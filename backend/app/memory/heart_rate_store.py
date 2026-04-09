from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.db import get_connection
from app.models import HeartRateReading, HeartRateStatus
from app.memory.session_store import get_app_user_id_for_session, get_session_optional


def _age_seconds(timestamp: datetime | None) -> int | None:
    if timestamp is None:
        return None
    now = datetime.now(timezone.utc)
    delta = now - timestamp.astimezone(timezone.utc)
    return max(int(delta.total_seconds()), 0)


def classify_heart_rate_status(age_sec: int | None) -> HeartRateStatus:
    if age_sec is None:
        return HeartRateStatus.unavailable
    if age_sec <= 30:
        return HeartRateStatus.fresh
    if age_sec <= 300:
        return HeartRateStatus.recent
    return HeartRateStatus.stale


def upsert_heart_rate(app_user_id: str, bpm: int, timestamp: datetime | None) -> HeartRateReading:
    reading_time = timestamp or datetime.now(timezone.utc)
    age_sec = _age_seconds(reading_time)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO heart_rate_cache (profile_id, bpm, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET
                bpm = excluded.bpm,
                timestamp = excluded.timestamp
            """,
            (app_user_id, bpm, reading_time.isoformat()),
        )
        conn.execute(
            """
            INSERT INTO app_user_heart_rate_events (app_user_id, bpm, timestamp, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (app_user_id, bpm, reading_time.isoformat(), datetime.now(timezone.utc).isoformat()),
        )
    return HeartRateReading(
        app_user_id=app_user_id,
        profile_id=app_user_id,
        bpm=bpm,
        timestamp=reading_time,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def get_latest_heart_rate(app_user_id: str) -> HeartRateReading:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT profile_id, bpm, timestamp FROM heart_rate_cache WHERE profile_id = ?",
            (app_user_id,),
        ).fetchone()
    if row is None:
        return HeartRateReading(app_user_id=app_user_id, profile_id=app_user_id, status=HeartRateStatus.unavailable)

    timestamp = datetime.fromisoformat(row["timestamp"])
    age_sec = _age_seconds(timestamp)
    return HeartRateReading(
        app_user_id=app_user_id,
        profile_id=app_user_id,
        bpm=row["bpm"],
        timestamp=timestamp,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def append_role_heart_rate(role_id: str, bpm: int, timestamp: datetime | None) -> HeartRateReading:
    session = get_session_optional(role_id)
    if session is None:
        raise HTTPException(status_code=404, detail="role not found")

    app_user_id = session.app_user_id or session.profile_id
    reading_time = timestamp or datetime.now(timezone.utc)
    reading = upsert_heart_rate(app_user_id, bpm, reading_time)
    created_at = datetime.now(timezone.utc)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO role_heart_rate_latest (role_id, bpm, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(role_id) DO UPDATE SET
                bpm = excluded.bpm,
                timestamp = excluded.timestamp
            """,
            (role_id, bpm, reading_time.isoformat()),
        )
        conn.execute(
            """
            INSERT INTO role_heart_rate_events (role_id, bpm, timestamp, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (role_id, bpm, reading_time.isoformat(), created_at.isoformat()),
        )
    return reading.model_copy(update={"role_id": role_id, "app_user_id": app_user_id, "profile_id": app_user_id})


def get_latest_role_heart_rate(role_id: str) -> HeartRateReading:
    app_user_id = get_app_user_id_for_session(role_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT bpm, timestamp FROM role_heart_rate_latest WHERE role_id = ?",
            (role_id,),
        ).fetchone()
    if row is None:
        return HeartRateReading(role_id=role_id, app_user_id=app_user_id, profile_id=app_user_id, status=HeartRateStatus.unavailable)
    timestamp = datetime.fromisoformat(row["timestamp"])
    age_sec = _age_seconds(timestamp)
    return HeartRateReading(
        role_id=role_id,
        app_user_id=app_user_id,
        profile_id=app_user_id,
        bpm=row["bpm"],
        timestamp=timestamp,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def list_role_heart_rate_events(role_id: str) -> list[HeartRateReading]:
    app_user_id = get_app_user_id_for_session(role_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT bpm, timestamp
            FROM role_heart_rate_events
            WHERE role_id = ?
            ORDER BY id ASC
            """,
            (role_id,),
        ).fetchall()
    readings: list[HeartRateReading] = []
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        age_sec = _age_seconds(timestamp)
        readings.append(
            HeartRateReading(
                role_id=role_id,
                app_user_id=app_user_id,
                profile_id=app_user_id,
                bpm=row["bpm"],
                timestamp=timestamp,
                age_sec=age_sec,
                status=classify_heart_rate_status(age_sec),
            )
        )
    return readings


def list_app_user_heart_rate_events(app_user_id: str) -> list[HeartRateReading]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT bpm, timestamp
            FROM app_user_heart_rate_events
            WHERE app_user_id = ?
            ORDER BY id ASC
            """,
            (app_user_id,),
        ).fetchall()
    readings: list[HeartRateReading] = []
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        age_sec = _age_seconds(timestamp)
        readings.append(
            HeartRateReading(
                app_user_id=app_user_id,
                profile_id=app_user_id,
                bpm=row["bpm"],
                timestamp=timestamp,
                age_sec=age_sec,
                status=classify_heart_rate_status(age_sec),
            )
        )
    return readings


def delete_role_heart_rate_events(role_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM role_heart_rate_events WHERE role_id = ?", (role_id,))
        conn.execute("DELETE FROM role_heart_rate_latest WHERE role_id = ?", (role_id,))
