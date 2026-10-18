"""Domain service for calendar events, RFC 5545 recurring routines, habit confirmations, and continuity."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.contracts.common import PrivacyScope, SensitivityLevel
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.base import utcnow
from app.models.event import Event, Routine, RoutineConfirmation, RoutineOccurrence
from app.services.audit_service import AuditService
from app.temporal.identity import OccurrenceIdentityGenerator
from app.temporal.recurrence import RecurrenceService
from app.temporal.timezone import TimezoneService, UTC


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is offset-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EventService:
    """Service governing calendar events, recurring habit routines, discrete occurrences, and confirmations."""

    # -------------------------------------------------------------------------
    # One-Time Event Management
    # -------------------------------------------------------------------------

    @classmethod
    async def create_one_time_event(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        local_start: str,
        local_end: Optional[str] = None,
        timezone_name: str = "Asia/Kolkata",
        status: str = "PLANNED",
        event_type: str = "ONE_TIME",
        description: Optional[str] = None,
        notes: Optional[str] = None,
        privacy_scope: str = "PERSONAL",
        sensitivity: int = 30,
        confirmed_at: Optional[datetime] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Event:
        """
        Create a discrete calendar event or certified historical event.
        Enforces Section 15 invariants: planned events start as PLANNED and are never COMPLETED without confirmation.
        """
        clean_title = title.strip()
        if not clean_title:
            raise ValidationError("Event title cannot be empty.")

        # Validate timezone
        TimezoneService.validate_or_raise(timezone_name)

        # Parse and convert timestamps
        naive_start = RecurrenceService.parse_iso_or_datetime(local_start)
        utc_start = TimezoneService.to_utc(naive_start, timezone_name)

        utc_end = None
        if local_end:
            naive_end = RecurrenceService.parse_iso_or_datetime(local_end)
            utc_end = TimezoneService.to_utc(naive_end, timezone_name)
            if utc_end < utc_start:
                raise ValidationError("Event local_end cannot be before local_start.")

        clean_status = status.upper()
        clean_type = event_type.upper()

        # Invariant: If marked COMPLETED, set confirmed_at
        if clean_status in ("COMPLETED", "CONFIRMED") and confirmed_at is None:
            confirmed_at = utcnow()
        elif clean_status == "PLANNED":
            confirmed_at = None

        event = Event(
            user_id=user_id,
            title=clean_title,
            description=description.strip() if description else None,
            event_type=clean_type,
            status=clean_status,
            local_start=naive_start.isoformat(),
            local_end=naive_end.isoformat() if local_end else None,
            utc_start=utc_start,
            utc_end=utc_end,
            timezone=timezone_name,
            privacy_scope=privacy_scope,
            sensitivity=sensitivity,
            notes=notes.strip() if notes else None,
            confirmed_at=confirmed_at,
        )
        db.add(event)
        await db.flush()

        await AuditService.record_event(
            session=db,
            action_type="event.create",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"event:{event.id}",
            details={"event_id": str(event.id), "title": clean_title, "status": clean_status},
        )
        await db.commit()
        return await cls.get_event(db, event.id, user_id)

    @classmethod
    async def get_event(
        cls,
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Event:
        """Fetch event with strict user-tenant ownership enforcement."""
        stmt = select(Event).where(Event.id == event_id).execution_options(populate_existing=True)
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()

        if event is None:
            raise EntityNotFoundError("Event", event_id)

        if event.user_id != user_id:
            raise PermissionDeniedError("Access denied: Event belongs to another user.")

        return event

    @classmethod
    async def confirm_event(
        cls,
        db: AsyncSession,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        notes: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Event:
        """Certify that a one-time event took place, transitioning status to COMPLETED."""
        event = await cls.get_event(db, event_id, user_id)

        event.status = "COMPLETED"
        event.confirmed_at = utcnow()
        if notes:
            event.notes = notes.strip()
        event.updated_at = utcnow()

        await AuditService.record_event(
            session=db,
            action_type="event.confirm",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"event:{event.id}",
            details={"event_id": str(event.id), "status": "COMPLETED"},
        )
        await db.commit()
        return await cls.get_event(db, event.id, user_id)

    @classmethod
    async def list_events(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        from_utc: Optional[datetime] = None,
        to_utc: Optional[datetime] = None,
    ) -> List[Event]:
        """List events for user with optional status and temporal filtering."""
        stmt = select(Event).where(Event.user_id == user_id).order_by(Event.utc_start.asc())
        if status:
            stmt = stmt.where(Event.status == status.upper())
        if from_utc:
            stmt = stmt.where(Event.utc_start >= ensure_utc(from_utc))
        if to_utc:
            stmt = stmt.where(Event.utc_start <= ensure_utc(to_utc))

        res = await db.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Recurring Routine Management
    # -------------------------------------------------------------------------

    @classmethod
    async def create_routine(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        recurrence_rule: str,
        dtstart_local: str,
        target_time: Optional[str] = None,
        timezone_name: str = "Asia/Kolkata",
        description: Optional[str] = None,
        check_in_policy: str = "once_per_occurrence",
        privacy_scope: str = "PERSONAL",
        sensitivity: int = 30,
        expand_days: int = 30,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> Routine:
        """
        Create a standing recurring habit routine and generate initial discrete PLANNED occurrences.
        """
        clean_title = title.strip()
        if not clean_title:
            raise ValidationError("Routine title cannot be empty.")

        # Validate timezone
        TimezoneService.validate_or_raise(timezone_name)

        # Validate start datetime
        start_naive = RecurrenceService.parse_iso_or_datetime(dtstart_local)

        # Validate recurrence rule with expansion test
        try:
            RecurrenceService.expand_recurrence(
                routine_id=uuid.uuid4(),
                rule_version=1,
                rrule_string=recurrence_rule,
                dtstart_local=start_naive,
                timezone=timezone_name,
                max_occurrences=10,
            )
        except Exception as exc:
            raise ValidationError(f"Invalid RFC 5545 recurrence rule '{recurrence_rule}': {exc}") from exc

        routine = Routine(
            user_id=user_id,
            title=clean_title,
            description=description.strip() if description else None,
            recurrence_rule=recurrence_rule,
            dtstart_local=start_naive.isoformat(),
            target_time=target_time,
            timezone=timezone_name,
            rule_version=1,
            is_active=True,
            check_in_policy=check_in_policy,
            privacy_scope=privacy_scope,
            sensitivity=sensitivity,
        )
        db.add(routine)
        await db.flush()

        # Audit log creation
        await AuditService.record_event(
            session=db,
            action_type="routine.create",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"routine:{routine.id}",
            details={"routine_id": str(routine.id), "title": clean_title, "rrule": recurrence_rule},
        )
        await db.commit()

        # Expand and populate initial occurrences
        await cls.expand_and_sync_occurrences(db, routine.id, user_id, days_ahead=expand_days)
        return await cls.get_routine(db, routine.id, user_id)

    @classmethod
    async def get_routine(
        cls,
        db: AsyncSession,
        routine_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Routine:
        """Fetch routine with strict user-tenant ownership enforcement."""
        stmt = (
            select(Routine)
            .where(Routine.id == routine_id)
            .options(selectinload(Routine.occurrences))
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        routine = res.scalar_one_or_none()

        if routine is None:
            raise EntityNotFoundError("Routine", routine_id)

        if routine.user_id != user_id:
            raise PermissionDeniedError("Access denied: Routine belongs to another user.")

        return routine

    @classmethod
    async def list_routines(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[Routine]:
        """List routines for user."""
        stmt = (
            select(Routine)
            .where(Routine.user_id == user_id)
            .options(selectinload(Routine.occurrences))
            .order_by(Routine.created_at.desc())
        )
        if is_active is not None:
            stmt = stmt.where(Routine.is_active == is_active)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def expand_and_sync_occurrences(
        cls,
        db: AsyncSession,
        routine_id: uuid.UUID,
        user_id: uuid.UUID,
        days_ahead: int = 30,
    ) -> List[RoutineOccurrence]:
        """
        Derive discrete occurrences from a routine using RFC 5545 expansion and deterministic SHA-256 identities.
        Generated occurrences always start in PLANNED state (never completed!).
        """
        routine = await cls.get_routine(db, routine_id, user_id)
        start_naive = RecurrenceService.parse_iso_or_datetime(routine.dtstart_local)
        until_dt = start_naive + timedelta(days=days_ahead)
        until_utc = TimezoneService.to_utc(until_dt, routine.timezone)

        expanded = RecurrenceService.expand_recurrence(
            routine_id=routine.id,
            rule_version=routine.rule_version,
            rrule_string=routine.recurrence_rule,
            dtstart_local=start_naive,
            timezone=routine.timezone,
            max_occurrences=100,
            window_end_utc=until_utc,
        )

        # Existing occurrence keys for this routine
        existing_stmt = select(RoutineOccurrence.occurrence_key).where(
            RoutineOccurrence.routine_id == routine.id
        )
        res = await db.execute(existing_stmt)
        existing_keys = set(res.scalars().all())

        new_occurrences: List[RoutineOccurrence] = []
        for occ in expanded:
            occ_key = occ.occurrence_key
            if occ_key not in existing_keys:
                local_dt = RecurrenceService.parse_iso_or_datetime(occ.local_time)
                utc_dt = datetime.fromisoformat(occ.utc_instant.replace("Z", "+00:00"))
                ro = RoutineOccurrence(
                    routine_id=routine.id,
                    user_id=user_id,
                    occurrence_key=occ_key,
                    scheduled_date=local_dt.date().isoformat(),
                    local_time=occ.local_time,
                    utc_instant=utc_dt,
                    timezone=routine.timezone,
                    status="PLANNED",
                )
                db.add(ro)
                new_occurrences.append(ro)
                existing_keys.add(occ_key)

        if new_occurrences:
            await db.commit()

        # Re-fetch occurrences
        stmt = (
            select(RoutineOccurrence)
            .where(RoutineOccurrence.routine_id == routine.id)
            .options(selectinload(RoutineOccurrence.confirmation))
            .order_by(RoutineOccurrence.utc_instant.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Occurrence Check-in & Confirmation Management
    # -------------------------------------------------------------------------

    @classmethod
    async def get_occurrence(
        cls,
        db: AsyncSession,
        occurrence_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> RoutineOccurrence:
        """Fetch discrete occurrence with ownership enforcement."""
        stmt = (
            select(RoutineOccurrence)
            .where(RoutineOccurrence.id == occurrence_id)
            .options(
                selectinload(RoutineOccurrence.routine),
                selectinload(RoutineOccurrence.confirmation),
            )
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        occ = res.scalar_one_or_none()

        if occ is None:
            raise EntityNotFoundError("RoutineOccurrence", occurrence_id)

        if occ.user_id != user_id:
            raise PermissionDeniedError("Access denied: Occurrence belongs to another user.")

        return occ

    @classmethod
    async def confirm_occurrence(
        cls,
        db: AsyncSession,
        occurrence_id: uuid.UUID,
        user_id: uuid.UUID,
        confirmed_by: str = "user",
        notes: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> RoutineOccurrence:
        """
        Record user confirmation certifying that an occurrence took place.
        Transitions occurrence state from PLANNED to COMPLETED and sets routine.last_confirmed_at.
        """
        occ = await cls.get_occurrence(db, occurrence_id, user_id)

        now = utcnow()
        occ.status = "COMPLETED"
        occ.resolved_at = now
        occ.updated_at = now

        # Add or update RoutineConfirmation
        if occ.confirmation:
            occ.confirmation.confirmed_at = now
            occ.confirmation.confirmed_by = confirmed_by
            occ.confirmation.notes = notes.strip() if notes else None
        else:
            conf = RoutineConfirmation(
                occurrence_id=occ.id,
                user_id=user_id,
                confirmed_at=now,
                confirmed_by=confirmed_by,
                notes=notes.strip() if notes else None,
            )
            db.add(conf)

        # Update parent routine last_confirmed_at
        occ.routine.last_confirmed_at = now
        occ.routine.updated_at = now

        await AuditService.record_event(
            session=db,
            action_type="routine.confirm",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"occurrence:{occ.id}",
            details={"occurrence_id": str(occ.id), "status": "COMPLETED"},
        )
        await db.commit()
        return await cls.get_occurrence(db, occ.id, user_id)

    @classmethod
    async def record_check_in(
        cls,
        db: AsyncSession,
        occurrence_id: uuid.UUID,
        user_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
    ) -> RoutineOccurrence:
        """
        Record proactive check-in (e.g. 'How is your fasting going today?').
        Sets last_check_in_at to deduplicate notifications and prevent duplicate questions (PRD 15.9).
        """
        occ = await cls.get_occurrence(db, occurrence_id, user_id)
        now = utcnow()

        occ.last_check_in_at = now
        occ.prompted_at = occ.prompted_at or now
        if occ.status == "PLANNED":
            occ.status = "PROMPTED"
        occ.updated_at = now

        await AuditService.record_event(
            session=db,
            action_type="routine.check_in",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"occurrence:{occ.id}",
            details={"occurrence_id": str(occ.id), "status": occ.status},
        )
        await db.commit()
        return await cls.get_occurrence(db, occ.id, user_id)

    # -------------------------------------------------------------------------
    # Habit Query & Continuity ("When was my last fasting?", PRD 15.6)
    # -------------------------------------------------------------------------

    @classmethod
    async def query_last_habit(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        habit_name: str,
    ) -> Dict[str, Any]:
        """
        Execute Section 15.6 Habit Query:
        1. Searches confirmed historical events first.
        2. Searches confirmed recurring routine occurrences.
        3. Identifies active routine schedules.
        4. Accurately distinguishes confirmed historical completions from unconfirmed plans.
        """
        clean_name = habit_name.strip().lower()
        if not clean_name:
            raise ValidationError("Habit name cannot be empty.")

        # 1. Search confirmed one-time events
        event_stmt = (
            select(Event)
            .where(
                Event.user_id == user_id,
                Event.title.ilike(f"%{clean_name}%"),
                Event.status.in_(["COMPLETED", "CONFIRMED"]),
            )
            .order_by(Event.utc_start.desc())
        )
        event_res = await db.execute(event_stmt)
        confirmed_events = list(event_res.scalars().all())

        # 2. Search confirmed routine occurrences
        occ_stmt = (
            select(RoutineOccurrence)
            .join(Routine, RoutineOccurrence.routine_id == Routine.id)
            .where(
                RoutineOccurrence.user_id == user_id,
                Routine.title.ilike(f"%{clean_name}%"),
                RoutineOccurrence.status.in_(["COMPLETED", "CONFIRMED"]),
            )
            .options(selectinload(RoutineOccurrence.routine))
            .order_by(RoutineOccurrence.utc_instant.desc())
        )
        occ_res = await db.execute(occ_stmt)
        confirmed_occs = list(occ_res.scalars().all())

        # 3. Find active routines for this habit
        routine_stmt = (
            select(Routine)
            .where(
                Routine.user_id == user_id,
                Routine.title.ilike(f"%{clean_name}%"),
                Routine.is_active == True,
            )
            .options(selectinload(Routine.occurrences))
        )
        r_res = await db.execute(routine_stmt)
        active_routines = list(r_res.scalars().all())

        candidates: List[Tuple[datetime, str, Any]] = []
        for ev in confirmed_events:
            candidates.append((ev.utc_start, "ONE_TIME_EVENT", ev))
        for oc in confirmed_occs:
            candidates.append((oc.utc_instant, "ROUTINE_OCCURRENCE", oc))

        candidates.sort(key=lambda x: x[0], reverse=True)

        # Check today's occurrence status if an active routine exists
        today_iso = date.today().isoformat()
        current_occ_status = "NONE"
        today_occ = None
        for r in active_routines:
            for o in r.occurrences:
                if o.scheduled_date == today_iso:
                    today_occ = o
                    current_occ_status = o.status
                    break

        if candidates:
            latest_dt, record_type, record = candidates[0]
            date_str = latest_dt.strftime("%A, %B %d, %Y")
            has_history = True

            if active_routines:
                r_title = active_routines[0].title
                msg = (
                    f"Your last confirmed {habit_name} day was {date_str}. "
                    f"You also have an active recurring {r_title} routine, "
                    f"but today's occurrence has not yet been confirmed."
                    if current_occ_status in ("PLANNED", "PROMPTED", "NONE")
                    else f"Your last confirmed {habit_name} day was {date_str}."
                )
            else:
                msg = f"Your last confirmed {habit_name} day was {date_str}."

            return {
                "habit_name": habit_name,
                "has_confirmed_history": True,
                "last_confirmed_at": latest_dt,
                "last_confirmed_date": date_str,
                "last_confirmed_type": record_type,
                "has_active_routine": bool(active_routines),
                "active_routine_details": {
                    "routine_id": str(active_routines[0].id),
                    "title": active_routines[0].title,
                    "recurrence_rule": active_routines[0].recurrence_rule,
                } if active_routines else None,
                "current_occurrence_status": current_occ_status,
                "formatted_message": msg,
            }
        else:
            # No confirmed history found
            if active_routines:
                msg = (
                    f"I have a {habit_name} routine scheduled, "
                    f"but I do not have a confirmed completed {habit_name} day in memory."
                )
            else:
                msg = f"I do not have a confirmed completed {habit_name} day in memory."

            return {
                "habit_name": habit_name,
                "has_confirmed_history": False,
                "last_confirmed_at": None,
                "last_confirmed_date": None,
                "last_confirmed_type": None,
                "has_active_routine": bool(active_routines),
                "active_routine_details": {
                    "routine_id": str(active_routines[0].id),
                    "title": active_routines[0].title,
                    "recurrence_rule": active_routines[0].recurrence_rule,
                } if active_routines else None,
                "current_occurrence_status": current_occ_status,
                "formatted_message": msg,
            }
