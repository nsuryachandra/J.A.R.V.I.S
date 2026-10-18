"""Proactive Intelligence Service: quiet hours, contextual meal check-ins, briefings, and anti-nagging throttling."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.base import utcnow
from app.models.event import Event, Routine, RoutineOccurrence
from app.models.proactive import ProactiveNotification
from app.models.task import Task
from app.models.user import User, UserProfile
from app.services.audit_service import AuditService
from app.services.event_service import EventService
from app.services.task_service import TaskService
from app.temporal.timezone import TimezoneService, UTC


class ProactiveService:
    """Core domain engine for proactive behavior, quiet hours, briefings, and anti-nagging rules."""

    MAX_DAILY_NOTIFICATIONS = 20
    MIN_COOLDOWN_MINUTES = 15

    # -------------------------------------------------------------------------
    # Profile & Preferences Helpers
    # -------------------------------------------------------------------------

    @classmethod
    async def get_user_and_profile(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Tuple[User, UserProfile]:
        """Fetch user and their profile with eager loading."""
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.profile))
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if user is None:
            raise EntityNotFoundError("User", user_id)

        profile = user.profile
        if profile is None:
            # Create default profile if missing
            profile = UserProfile(
                user_id=user.id,
                display_name=user.email.split("@")[0],
                preferred_address_form="sir",
                quiet_hours_start="22:00:00",
                quiet_hours_end="07:00:00",
                meal_check_in_enabled=True,
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)

        return user, profile

    @classmethod
    def format_address(
        cls,
        profile: UserProfile,
        prefix: str = "",
        suffix: str = "",
    ) -> str:
        """
        Incorporate preferred form of address naturally without robotic repetition (PRD 6.5).
        Returns formatted address token or empty string if neutral/disabled.
        """
        form = (profile.preferred_address_form or "").strip().lower()
        if not form or form in ("neutral", "none", "no"):
            return ""
        # Return properly capitalized address form with contextual padding
        formatted_form = form
        if prefix and suffix:
            return f"{prefix}{formatted_form}{suffix}"
        if prefix:
            return f"{prefix}{formatted_form}"
        if suffix:
            return f"{formatted_form}{suffix}"
        return formatted_form

    # -------------------------------------------------------------------------
    # Quiet Hours & Throttling
    # -------------------------------------------------------------------------

    @classmethod
    def parse_time_str(cls, time_str: Optional[str], default_time: time) -> time:
        """Safely parse HH:MM or HH:MM:SS string to time object."""
        if not time_str:
            return default_time
        try:
            parts = time_str.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(parts[2]) if len(parts) > 2 else 0
            return time(hour, minute, second)
        except Exception:
            return default_time

    @classmethod
    def is_quiet_hours_active(
        cls,
        profile: UserProfile,
        tz_name: str,
        check_dt: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluate if quiet hours are currently in effect in the user's local timezone.
        Handles both normal windows (01:00-05:00) and midnight crossover windows (22:00-07:00).
        """
        start_time = cls.parse_time_str(profile.quiet_hours_start, time(22, 0, 0))
        end_time = cls.parse_time_str(profile.quiet_hours_end, time(7, 0, 0))

        target_dt = check_dt or utcnow()
        local_dt = TimezoneService.to_local(target_dt, tz_name)
        curr_time = local_dt.time()

        window_desc = f"{start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}"

        if start_time == end_time:
            # Quiet hours effectively disabled
            return False, window_desc

        if start_time < end_time:
            # Standard window within single day (e.g. 01:00 to 06:00)
            is_active = start_time <= curr_time <= end_time
        else:
            # Midnight-crossing window (e.g. 22:00 to 07:00)
            is_active = curr_time >= start_time or curr_time <= end_time

        return is_active, window_desc

    @classmethod
    async def check_throttle(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        priority: str = "NORMAL",
        current_dt: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Enforce anti-nagging rate limits and cooldown periods (PRD 16.4 & 16.5).
        URGENT priority notifications bypass throttling.
        """
        if priority.upper() == "URGENT":
            return False, None

        now = current_dt or utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Check daily notification limit
        effective_time = func.coalesce(ProactiveNotification.dispatched_at, ProactiveNotification.created_at)
        daily_count_stmt = (
            select(func.count(ProactiveNotification.id))
            .where(
                ProactiveNotification.user_id == user_id,
                effective_time >= today_start,
                ProactiveNotification.status == "DISPATCHED",
            )
        )
        res = await db.execute(daily_count_stmt)
        dispatched_today = res.scalar_one() or 0

        if dispatched_today >= cls.MAX_DAILY_NOTIFICATIONS:
            return True, f"Daily limit of {cls.MAX_DAILY_NOTIFICATIONS} notifications reached."

        # 2. Check cooldown window (anti-nagging)
        cooldown_threshold = now - timedelta(minutes=cls.MIN_COOLDOWN_MINUTES)
        recent_stmt = (
            select(ProactiveNotification)
            .where(
                ProactiveNotification.user_id == user_id,
                effective_time >= cooldown_threshold,
                ProactiveNotification.status == "DISPATCHED",
            )
            .order_by(effective_time.desc())
        )
        recent_res = await db.execute(recent_stmt)
        recent_notification = recent_res.scalars().first()

        if recent_notification:
            return True, f"Cooldown active: notification dispatched less than {cls.MIN_COOLDOWN_MINUTES} minutes ago."

        return False, None

    # -------------------------------------------------------------------------
    # Contextual Meal Check-in (PRD 6.6)
    # -------------------------------------------------------------------------

    @classmethod
    async def evaluate_meal_check_in(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_dt: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Optional[ProactiveNotification]:
        """
        PRD Section 6.6: Contextual meal check-in around 2 PM.
        Rules:
        - Enabled via meal_check_in_enabled.
        - Local time between 13:30 and 15:00.
        - Respects quiet hours.
        - Deduplicated once per day.
        - Does not claim user has/has not eaten, does not give medical advice.
        """
        user, profile = await cls.get_user_and_profile(db, user_id)
        if not profile.meal_check_in_enabled:
            return None

        now = current_dt or utcnow()
        local_dt = TimezoneService.to_local(now, user.timezone)
        curr_time = local_dt.time()

        # Lunch window: 13:30 to 15:00 (approx 2 PM)
        lunch_start = time(13, 30, 0)
        lunch_end = time(15, 0, 0)

        if not (lunch_start <= curr_time <= lunch_end):
            return None

        # Check deduplication for today's date
        today_date_str = local_dt.date().isoformat()
        dedup_key = f"meal_check_in:{user.id}:{today_date_str}"

        existing_stmt = select(ProactiveNotification).where(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.deduplication_key == dedup_key,
        )
        res = await db.execute(existing_stmt)
        if res.scalars().first() is not None:
            return None  # Already prompted today

        # Quiet hours evaluation
        in_quiet_hours, quiet_win = cls.is_quiet_hours_active(profile, user.timezone, now)
        is_throttled, throttle_reason = await cls.check_throttle(db, user_id, priority="NORMAL", current_dt=now)

        # Build address token (e.g. ", sir")
        addr = cls.format_address(profile, prefix=", ")
        message = f"Have you eaten yet{addr}?"

        status = "DISPATCHED"
        suppression_reason = None
        dispatched_at = now

        if in_quiet_hours:
            status = "SUPPRESSED_QUIET_HOURS"
            suppression_reason = f"Quiet hours active ({quiet_win})"
            dispatched_at = None
        elif is_throttled:
            status = "SUPPRESSED_THROTTLED"
            suppression_reason = throttle_reason
            dispatched_at = None

        notification = ProactiveNotification(
            user_id=user_id,
            notification_type="MEAL_CHECK_IN",
            channel="IN_APP",
            priority="NORMAL",
            title="Lunch Check-In",
            content=message,
            context_data={
                "local_time": local_dt.isoformat(),
                "meal_type": "lunch",
            },
            status=status,
            suppression_reason=suppression_reason,
            deduplication_key=dedup_key,
            dispatched_at=dispatched_at,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        await AuditService.record_event(
            session=db,
            action_type="proactive.meal_check_in",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"notification:{notification.id}",
            details={"status": status, "dedup_key": dedup_key},
        )
        await db.commit()
        return notification

    # -------------------------------------------------------------------------
    # Morning & Evening Briefings (PRD 16.1 & 16.2)
    # -------------------------------------------------------------------------

    @classmethod
    async def generate_morning_briefing(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_dt: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        PRD Section 16.1: Assembles structured morning briefing.
        - Date and local time in Asia/Kolkata
        - Today's calendar events
        - Routine habits scheduled for today
        - Pending tasks and priority recommendations
        """
        user, profile = await cls.get_user_and_profile(db, user_id)
        now = current_dt or utcnow()
        local_dt = TimezoneService.to_local(now, user.timezone)
        today_date = local_dt.date()
        today_date_str = today_date.isoformat()
        formatted_date = local_dt.strftime("%A, %B %d, %Y")
        time_str = local_dt.strftime("%I:%M %p")

        # 1. Fetch today's calendar events
        start_of_day_local = datetime.combine(today_date, time.min)
        end_of_day_local = datetime.combine(today_date, time.max)
        start_of_day_utc = TimezoneService.to_utc(start_of_day_local, user.timezone)
        end_of_day_utc = TimezoneService.to_utc(end_of_day_local, user.timezone)

        events = await EventService.list_events(
            db=db,
            user_id=user_id,
            from_utc=start_of_day_utc,
            to_utc=end_of_day_utc,
        )

        # 2. Fetch today's routine occurrences
        routines = await EventService.list_routines(db, user_id, is_active=True)
        today_occurrences = []
        for r in routines:
            for occ in r.occurrences:
                if occ.scheduled_date == today_date_str:
                    today_occurrences.append({
                        "routine_title": r.title,
                        "occurrence_id": str(occ.id),
                        "status": occ.status,
                        "local_time": occ.local_time,
                    })

        # 3. Fetch pending work
        pending_work = await TaskService.query_pending_work(db, user_id, include_yesterday=True)

        # 4. Format greeting and briefing
        addr = cls.format_address(profile, prefix=", ")
        greeting = f"Good morning{addr}. Today is {formatted_date}, {time_str} ({user.timezone})."

        items: List[str] = [greeting]
        if events:
            items.append(f"You have {len(events)} calendar event(s) scheduled for today:")
            for ev in events:
                items.append(f"• {ev.title} at {ev.local_start} [{ev.status}]")
        else:
            items.append("Your calendar is clear for today.")

        if today_occurrences:
            items.append(f"Scheduled routines for today:")
            for ro in today_occurrences:
                items.append(f"• {ro['routine_title']} [{ro['status']}]")

        summary = pending_work.get("summary", {})
        unfinished_count = summary.get("total_unfinished", 0)
        if unfinished_count > 0:
            items.append(f"You have {unfinished_count} pending task(s) carrying forward.")
        else:
            items.append("All primary tasks are up to date.")

        full_content = "\n".join(items)

        # Record notification with deduplication
        dedup_key = f"morning_briefing:{user.id}:{today_date_str}"
        existing_stmt = select(ProactiveNotification).where(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.deduplication_key == dedup_key,
        )
        res = await db.execute(existing_stmt)
        notification = res.scalars().first()

        if notification is None:
            notification = ProactiveNotification(
                user_id=user_id,
                notification_type="MORNING_BRIEFING",
                channel="IN_APP",
                priority="NORMAL",
                title="Morning Briefing",
                content=full_content,
                context_data={
                    "date": today_date_str,
                    "events_count": len(events),
                    "routines_count": len(today_occurrences),
                    "pending_tasks_count": unfinished_count,
                },
                status="DISPATCHED",
                deduplication_key=dedup_key,
                dispatched_at=now,
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            await AuditService.record_event(
                session=db,
                action_type="proactive.morning_briefing",
                decision="ALLOW",
                user_id=user_id,
                session_id=session_id,
                resource_scope=f"notification:{notification.id}",
                details={"date": today_date_str},
            )
            await db.commit()

        return {
            "briefing_type": "MORNING_BRIEFING",
            "date": today_date_str,
            "formatted_date": formatted_date,
            "timezone": user.timezone,
            "greeting": greeting,
            "content": full_content,
            "events_today": [{"id": str(e.id), "title": e.title, "local_start": e.local_start} for e in events],
            "routines_today": today_occurrences,
            "pending_work": pending_work,
            "notification_id": str(notification.id) if notification else None,
        }

    @classmethod
    async def generate_evening_briefing(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_dt: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        PRD Section 16.2: Assembles structured evening briefing.
        - Completed tasks recap
        - Unfinished tasks & blockers
        - Upcoming deadlines for tomorrow
        """
        user, profile = await cls.get_user_and_profile(db, user_id)
        now = current_dt or utcnow()
        local_dt = TimezoneService.to_local(now, user.timezone)
        today_date = local_dt.date()
        today_date_str = today_date.isoformat()
        tomorrow_date = today_date + timedelta(days=1)
        formatted_date = local_dt.strftime("%A, %B %d, %Y")

        # 1. Fetch pending work
        pending_work = await TaskService.query_pending_work(db, user_id, include_yesterday=False)

        # 2. Fetch tasks completed today
        start_of_day_local = datetime.combine(today_date, time.min)
        start_of_day_utc = TimezoneService.to_utc(start_of_day_local, user.timezone)

        completed_stmt = select(Task).where(
            Task.user_id == user_id,
            Task.status.in_(["DONE", "COMPLETED"]),
            Task.completed_at >= start_of_day_utc,
        )
        c_res = await db.execute(completed_stmt)
        completed_tasks = list(c_res.scalars().all())

        # 3. Format greeting and briefing
        addr = cls.format_address(profile, prefix=", ")
        greeting = f"Good evening{addr}. Here is your recap for {formatted_date}."

        items: List[str] = [greeting]
        if completed_tasks:
            items.append(f"Completed today ({len(completed_tasks)} task(s)):")
            for t in completed_tasks:
                items.append(f"✓ {t.title}")
        else:
            items.append("No tasks were marked completed today.")

        blocked_tasks = pending_work.get("blocked", [])
        if blocked_tasks:
            items.append(f"Open blockers requiring attention ({len(blocked_tasks)}):")
            for t in blocked_tasks:
                reason = t.blockers[0].get("reason") if t.blockers else "Blocked"
                items.append(f"⚠ {t.title}: {reason}")

        in_progress = pending_work.get("in_progress", [])
        if in_progress:
            items.append(f"Active in-progress items ({len(in_progress)}):")
            for ip in in_progress:
                items.append(f"• {ip.title}")

        full_content = "\n".join(items)

        # Record notification with deduplication
        dedup_key = f"evening_briefing:{user.id}:{today_date_str}"
        existing_stmt = select(ProactiveNotification).where(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.deduplication_key == dedup_key,
        )
        res = await db.execute(existing_stmt)
        notification = res.scalars().first()

        if notification is None:
            notification = ProactiveNotification(
                user_id=user_id,
                notification_type="EVENING_BRIEFING",
                channel="IN_APP",
                priority="NORMAL",
                title="Evening Briefing",
                content=full_content,
                context_data={
                    "date": today_date_str,
                    "completed_count": len(completed_tasks),
                    "blockers_count": len(blocked_tasks),
                    "in_progress_count": len(in_progress),
                },
                status="DISPATCHED",
                deduplication_key=dedup_key,
                dispatched_at=now,
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            await AuditService.record_event(
                session=db,
                action_type="proactive.evening_briefing",
                decision="ALLOW",
                user_id=user_id,
                session_id=session_id,
                resource_scope=f"notification:{notification.id}",
                details={"date": today_date_str},
            )
            await db.commit()

        return {
            "briefing_type": "EVENING_BRIEFING",
            "date": today_date_str,
            "formatted_date": formatted_date,
            "timezone": user.timezone,
            "greeting": greeting,
            "content": full_content,
            "completed_today": [{"id": str(t.id), "title": t.title} for t in completed_tasks],
            "pending_work": pending_work,
            "notification_id": str(notification.id) if notification else None,
        }

    # -------------------------------------------------------------------------
    # Task Deadline Suggestions (PRD 16.3)
    # -------------------------------------------------------------------------

    @classmethod
    async def evaluate_task_deadline_suggestions(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_dt: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> List[ProactiveNotification]:
        """
        PRD Section 16.3: Proactive suggestions for tasks due within 24 hours.
        Includes relevance, evidence, suggested action, expected benefit, and whether approval is required.
        """
        user, profile = await cls.get_user_and_profile(db, user_id)
        now = current_dt or utcnow()
        horizon = now + timedelta(hours=24)

        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status.notin_(["DONE", "ARCHIVED"]),
                Task.due_at != None,
                Task.due_at <= horizon,
            )
            .order_by(Task.due_at.asc())
        )
        res = await db.execute(stmt)
        due_tasks = list(res.scalars().all())

        notifications: List[ProactiveNotification] = []
        for task in due_tasks:
            dedup_key = f"deadline_suggestion:{task.id}:{now.strftime('%Y-%m-%d')}"
            exist_stmt = select(ProactiveNotification).where(
                ProactiveNotification.user_id == user_id,
                ProactiveNotification.deduplication_key == dedup_key,
            )
            e_res = await db.execute(exist_stmt)
            if e_res.scalars().first() is not None:
                continue

            addr = cls.format_address(profile, prefix=", ")
            title = f"Upcoming Deadline: {task.title}"
            due_str = task.due_at.strftime("%Y-%m-%d %H:%M UTC") if task.due_at else "soon"
            content = (
                f"Task '{task.title}' is due {due_str}{addr}. "
                f"Status: {task.status}. "
                f"Suggested action: prioritize this deliverable before the deadline."
            )

            context_data = {
                "relevance": "Task deadline falls within 24 hours.",
                "evidence": f"Due at {due_str}.",
                "suggested_action": f"Focus on completing '{task.title}'.",
                "expected_benefit": "Avoids deadline breach.",
                "approval_required": False,
                "task_id": str(task.id),
            }

            in_quiet_hours, _ = cls.is_quiet_hours_active(profile, user.timezone, now)
            is_throttled, reason = await cls.check_throttle(db, user_id, priority="NORMAL", current_dt=now)

            status = "DISPATCHED"
            suppression_reason = None
            dispatched_at = now

            if in_quiet_hours:
                status = "SUPPRESSED_QUIET_HOURS"
                suppression_reason = "Quiet hours active"
                dispatched_at = None
            elif is_throttled:
                status = "SUPPRESSED_THROTTLED"
                suppression_reason = reason
                dispatched_at = None

            n = ProactiveNotification(
                user_id=user_id,
                notification_type="TASK_DEADLINE",
                channel="IN_APP",
                priority="HIGH" if task.priority == "HIGH" else "NORMAL",
                title=title,
                content=content,
                context_data=context_data,
                status=status,
                suppression_reason=suppression_reason,
                deduplication_key=dedup_key,
                dispatched_at=dispatched_at,
            )
            db.add(n)
            notifications.append(n)

        if notifications:
            await db.commit()
        return notifications

    # -------------------------------------------------------------------------
    # Evaluation Cycle & Notification Management
    # -------------------------------------------------------------------------

    @classmethod
    async def evaluate_proactive_rules(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        current_dt: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> List[ProactiveNotification]:
        """
        Run the complete proactive rule evaluation cycle for user:
        1. Contextual meal check-in
        2. Task deadline suggestions
        """
        results: List[ProactiveNotification] = []

        # 1. Meal check-in
        meal_n = await cls.evaluate_meal_check_in(db, user_id, current_dt=current_dt, session_id=session_id)
        if meal_n:
            results.append(meal_n)

        # 2. Task deadlines
        deadline_ns = await cls.evaluate_task_deadline_suggestions(
            db, user_id, current_dt=current_dt, session_id=session_id
        )
        results.extend(deadline_ns)

        return results

    @classmethod
    async def list_notifications(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        notification_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProactiveNotification]:
        """Fetch notifications with user isolation and optional filtering."""
        stmt = (
            select(ProactiveNotification)
            .where(ProactiveNotification.user_id == user_id)
            .order_by(ProactiveNotification.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(ProactiveNotification.status == status.upper())
        if notification_type:
            stmt = stmt.where(ProactiveNotification.notification_type == notification_type.upper())

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_notification(
        cls,
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProactiveNotification:
        """Fetch notification by ID with user ownership check."""
        stmt = select(ProactiveNotification).where(ProactiveNotification.id == notification_id)
        res = await db.execute(stmt)
        n = res.scalar_one_or_none()

        if n is None:
            raise EntityNotFoundError("ProactiveNotification", notification_id)

        if n.user_id != user_id:
            raise PermissionDeniedError("Access denied: Notification belongs to another user.")

        return n

    @classmethod
    async def dismiss_notification(
        cls,
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProactiveNotification:
        """Mark notification as DISMISSED."""
        n = await cls.get_notification(db, notification_id, user_id)
        n.status = "DISMISSED"
        n.dismissed_at = utcnow()
        n.updated_at = utcnow()
        await db.commit()
        return n

    @classmethod
    async def mark_as_read(
        cls,
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProactiveNotification:
        """Mark notification as READ."""
        n = await cls.get_notification(db, notification_id, user_id)
        n.status = "READ"
        n.read_at = utcnow()
        n.updated_at = utcnow()
        await db.commit()
        return n
