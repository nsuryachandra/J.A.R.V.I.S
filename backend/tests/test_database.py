"""Database integration tests verifying persistence, rollback, constraints, and relationships."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from app.core.database import check_database_health
from app.models.user import User, UserProfile


@pytest.mark.asyncio
async def test_database_health_check(test_engine: AsyncEngine):
    """Verify check_database_health executes SELECT 1 successfully."""
    is_healthy = await check_database_health(test_engine)
    assert is_healthy is True


@pytest.mark.asyncio
async def test_user_and_profile_persistence(db_session: AsyncSession):
    """Verify creating User and UserProfile with foreign key relationship and timestamps."""
    user = User(
        email="surya@example.com",
        hashed_password="secure-hashed-pw-test",
        timezone="Asia/Kolkata",
    )
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None
    assert user.created_at is not None

    profile = UserProfile(
        user_id=user.id,
        display_name="Surya",
        preferred_address_form="sir",
        meal_check_in_enabled=True,
    )
    db_session.add(profile)
    await db_session.commit()

    # Query back using select
    stmt = select(User).where(User.email == "surya@example.com")
    result = await db_session.execute(stmt)
    retrieved_user = result.scalar_one_or_none()

    assert retrieved_user is not None
    assert retrieved_user.email == "surya@example.com"
    assert retrieved_user.timezone == "Asia/Kolkata"
    assert retrieved_user.is_active is True

    # Test profile relationship
    stmt_profile = select(UserProfile).where(UserProfile.user_id == user.id)
    prof_res = await db_session.execute(stmt_profile)
    retrieved_profile = prof_res.scalar_one_or_none()

    assert retrieved_profile is not None
    assert retrieved_profile.display_name == "Surya"
    assert retrieved_profile.preferred_address_form == "sir"
    assert retrieved_profile.meal_check_in_enabled is True


@pytest.mark.asyncio
async def test_database_rollback_prevents_persistence(db_session: AsyncSession):
    """Verify that an explicit rollback prevents uncommitted entities from persisting."""
    user = User(
        email="rollback-user@example.com",
        hashed_password="pw",
    )
    db_session.add(user)
    await db_session.flush()

    # Roll back transaction
    await db_session.rollback()

    stmt = select(User).where(User.email == "rollback-user@example.com")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_user_unique_email_constraint(db_session: AsyncSession):
    """Verify that duplicate email addresses violate unique constraint."""
    user1 = User(email="duplicate@example.com", hashed_password="pw1")
    db_session.add(user1)
    await db_session.commit()

    user2 = User(email="duplicate@example.com", hashed_password="pw2")
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()
