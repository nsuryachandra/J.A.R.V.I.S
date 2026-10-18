"""Unit tests for ProactiveService: quiet hours, contextual meal check-ins, briefings, and anti-nagging throttling."""

import uuid
from datetime import datetime, time, timedelta, timezone
import pytest
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.event import Event, Routine, RoutineOccurrence
from app.models.proactive import ProactiveNotification
from app.models.task import Project, Task
from app.models.user import User, UserProfile
from app.services.event_service import EventService
from app.services.proactive_service import ProactiveService
from app.services.task_service import TaskService


@pytest.mark.asyncio
async def test_quiet_hours_evaluation(db_session):
    """Verify quiet hours evaluation with normal and midnight-crossing windows."""
    user = User(
        email="quiethours@jarvis.ai",
        hashed_password="hashedpassword",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.flush()

    # Case 1: Midnight-crossing window (22:00 to 07:00)
    profile1 = UserProfile(
        user_id=user.id,
        display_name="Test",
        quiet_hours_start="22:00:00",
        quiet_hours_end="07:00:00",
    )
    db_session.add(profile1)
    await db_session.commit()

    # 23:30 Asia/Kolkata -> Quiet hours ACTIVE (18:00 UTC)
    dt_active_night = datetime(2026, 10, 18, 18, 0, 0, tzinfo=timezone.utc)
    is_active, _ = ProactiveService.is_quiet_hours_active(profile1, "Asia/Kolkata", dt_active_night)
    assert is_active is True

    # 05:30 Asia/Kolkata -> Quiet hours ACTIVE (00:00 UTC)
    dt_active_morning = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
    is_active, _ = ProactiveService.is_quiet_hours_active(profile1, "Asia/Kolkata", dt_active_morning)
    assert is_active is True

    # 14:00 Asia/Kolkata -> Quiet hours INACTIVE (08:30 UTC)
    dt_inactive_day = datetime(2026, 10, 18, 8, 30, 0, tzinfo=timezone.utc)
    is_active, _ = ProactiveService.is_quiet_hours_active(profile1, "Asia/Kolkata", dt_inactive_day)
    assert is_active is False


@pytest.mark.asyncio
async def test_address_form_formatting():
    """Verify natural language form of address insertion and neutral fallback (PRD 6.5)."""
    p_sir = UserProfile(user_id=uuid.uuid4(), display_name="Tony", preferred_address_form="sir")
    assert ProactiveService.format_address(p_sir, prefix=", ") == ", sir"

    p_boss = UserProfile(user_id=uuid.uuid4(), display_name="Bruce", preferred_address_form="boss")
    assert ProactiveService.format_address(p_boss, prefix=", ") == ", boss"

    p_neutral = UserProfile(user_id=uuid.uuid4(), display_name="Alex", preferred_address_form="neutral")
    assert ProactiveService.format_address(p_neutral, prefix=", ") == ""

    p_none = UserProfile(user_id=uuid.uuid4(), display_name="Sam", preferred_address_form="none")
    assert ProactiveService.format_address(p_none, prefix=", ") == ""


@pytest.mark.asyncio
async def test_contextual_meal_check_in_lifecycle_and_deduplication(db_session):
    """
    Verify PRD Section 6.6:
    - Triggers at approx 2 PM (13:30 to 15:00) in user's timezone.
    - Deduplicates once per day.
    - Respects disabled setting.
    """
    user = User(
        email="mealuser@jarvis.ai",
        hashed_password="hashedpassword",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name="Meal Tester",
        preferred_address_form="sir",
        quiet_hours_start="22:00:00",
        quiet_hours_end="07:00:00",
        meal_check_in_enabled=True,
    )
    db_session.add(profile)
    await db_session.commit()

    # 1. At 14:00 Asia/Kolkata (08:30 UTC): Valid lunch window
    dt_lunch = datetime(2026, 10, 18, 8, 30, 0, tzinfo=timezone.utc)
    notification = await ProactiveService.evaluate_meal_check_in(db_session, user.id, current_dt=dt_lunch)
    assert notification is not None
    assert notification.notification_type == "MEAL_CHECK_IN"
    assert notification.status == "DISPATCHED"
    assert "Have you eaten yet, sir?" in notification.content

    # 2. Second evaluation at 14:30 on same day: Deduplicated (returns None)
    dt_lunch_repeat = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    dup = await ProactiveService.evaluate_meal_check_in(db_session, user.id, current_dt=dt_lunch_repeat)
    assert dup is None

    # 3. Outside lunch window (e.g. 10:00 Asia/Kolkata -> 04:30 UTC on next day)
    dt_morning = datetime(2026, 10, 19, 4, 30, 0, tzinfo=timezone.utc)
    outside = await ProactiveService.evaluate_meal_check_in(db_session, user.id, current_dt=dt_morning)
    assert outside is None

    # 4. Disabled preference
    profile.meal_check_in_enabled = False
    await db_session.commit()
    dt_lunch_day2 = datetime(2026, 10, 19, 8, 30, 0, tzinfo=timezone.utc)
    disabled_res = await ProactiveService.evaluate_meal_check_in(db_session, user.id, current_dt=dt_lunch_day2)
    assert disabled_res is None


@pytest.mark.asyncio
async def test_anti_nagging_throttle_and_cooldown(db_session):
    """Verify anti-nagging throttle and cooldown logic (PRD 16.4 & 16.5)."""
    uid = uuid.uuid4()
    now = datetime(2026, 10, 18, 10, 0, 0, tzinfo=timezone.utc)

    # Initially, no notifications -> not throttled
    throttled, _ = await ProactiveService.check_throttle(db_session, uid, priority="NORMAL", current_dt=now)
    assert throttled is False

    # Dispatch a notification at 10:00
    n = ProactiveNotification(
        user_id=uid,
        notification_type="SUGGESTION",
        channel="IN_APP",
        priority="NORMAL",
        title="Check",
        content="Check this",
        status="DISPATCHED",
        created_at=now,
        dispatched_at=now,
    )
    db_session.add(n)
    await db_session.commit()

    # 5 minutes later (10:05): Should be throttled due to cooldown window (<15m)
    now_5m = now + timedelta(minutes=5)
    throttled, reason = await ProactiveService.check_throttle(db_session, uid, priority="NORMAL", current_dt=now_5m)
    assert throttled is True
    assert "Cooldown active" in reason

    # URGENT priority bypasses throttle
    throttled_urgent, _ = await ProactiveService.check_throttle(db_session, uid, priority="URGENT", current_dt=now_5m)
    assert throttled_urgent is False

    # 20 minutes later (10:20): Cooldown expired -> not throttled
    now_20m = now + timedelta(minutes=20)
    throttled_later, _ = await ProactiveService.check_throttle(db_session, uid, priority="NORMAL", current_dt=now_20m)
    assert throttled_later is False


@pytest.mark.asyncio
async def test_morning_and_evening_briefings(db_session):
    """Verify morning and evening briefing generation with tasks, events, and routines (PRD 16.1 & 16.2)."""
    user = User(
        email="briefings@jarvis.ai",
        hashed_password="hashedpassword",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name="Commander",
        preferred_address_form="sir",
    )
    db_session.add(profile)
    await db_session.commit()

    # Pre-populate an event scheduled for today
    await EventService.create_one_time_event(
        db=db_session,
        user_id=user.id,
        title="Strategic Review",
        local_start="2026-10-18T11:00:00",
        timezone_name="Asia/Kolkata",
    )

    # Pre-populate a task completed today
    proj = await TaskService.create_project(db_session, user.id, "Core System")
    task1 = await TaskService.create_task(db_session, user.id, "Deploy Patch", project_id=proj.id)
    await TaskService.complete_task(
        db_session,
        task1.id,
        user.id,
        evidence_type="USER_CONFIRMATION",
        description="Deployed",
        verified_by="user",
    )

    # Pre-populate a pending blocked task
    task2 = await TaskService.create_task(db_session, user.id, "Security Audit", project_id=proj.id)
    await TaskService.add_blocker(db_session, task2.id, user.id, reason="Awaiting penetration test results")

    # 1. Generate morning briefing
    ref_morning = datetime(2026, 10, 18, 3, 30, 0, tzinfo=timezone.utc)  # 09:00 AM IST
    morning = await ProactiveService.generate_morning_briefing(db_session, user.id, current_dt=ref_morning)
    assert morning["briefing_type"] == "MORNING_BRIEFING"
    assert "Good morning, sir." in morning["greeting"]
    assert "Strategic Review" in morning["content"]
    assert morning["notification_id"] is not None

    # 2. Generate evening briefing
    ref_evening = datetime(2026, 10, 18, 14, 0, 0, tzinfo=timezone.utc)  # 07:30 PM IST
    evening = await ProactiveService.generate_evening_briefing(db_session, user.id, current_dt=ref_evening)
    assert evening["briefing_type"] == "EVENING_BRIEFING"
    assert "Good evening, sir." in evening["greeting"]
    assert "Deploy Patch" in evening["content"]
    assert "Awaiting penetration test results" in evening["content"]
    assert evening["notification_id"] is not None


@pytest.mark.asyncio
async def test_task_deadline_suggestions(db_session):
    """Verify PRD Section 16.3 task deadline proactive suggestions."""
    user = User(
        email="deadlines@jarvis.ai",
        hashed_password="hashedpassword",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.flush()

    now = datetime(2026, 10, 18, 8, 30, 0, tzinfo=timezone.utc)  # 14:00 IST
    due_soon = now + timedelta(hours=4)

    # Create task due in 4 hours
    task = await TaskService.create_task(
        db=db_session,
        user_id=user.id,
        title="Submit Tax Return",
        due_at=due_soon,
        priority="HIGH",
    )

    notifications = await ProactiveService.evaluate_task_deadline_suggestions(
        db_session,
        user.id,
        current_dt=now,
    )
    assert len(notifications) == 1
    n = notifications[0]
    assert n.notification_type == "TASK_DEADLINE"
    assert n.priority == "HIGH"
    assert "Submit Tax Return" in n.title
    assert n.context_data["approval_required"] is False
    assert "Avoids deadline breach" in n.context_data["expected_benefit"]


@pytest.mark.asyncio
async def test_notification_management_and_isolation(db_session):
    """Verify notification listing, dismissal, read marking, and user isolation."""
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    n = ProactiveNotification(
        user_id=uid_a,
        notification_type="SUGGESTION",
        channel="IN_APP",
        priority="NORMAL",
        title="Suggestion A",
        content="Personal suggestion for A",
        status="DISPATCHED",
    )
    db_session.add(n)
    await db_session.commit()

    # User A lists notifications
    list_a = await ProactiveService.list_notifications(db_session, uid_a)
    assert len(list_a) == 1
    assert list_a[0].id == n.id

    # User B cannot access User A's notification
    with pytest.raises(PermissionDeniedError):
        await ProactiveService.get_notification(db_session, n.id, uid_b)

    with pytest.raises(PermissionDeniedError):
        await ProactiveService.dismiss_notification(db_session, n.id, uid_b)

    # User A marks as read
    read_n = await ProactiveService.mark_as_read(db_session, n.id, uid_a)
    assert read_n.status == "READ"
    assert read_n.read_at is not None

    # User A dismisses notification
    dismissed = await ProactiveService.dismiss_notification(db_session, n.id, uid_a)
    assert dismissed.status == "DISMISSED"
    assert dismissed.dismissed_at is not None
