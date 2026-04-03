from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_connection
from app.models import HeartRateReading, HeartRateStatus


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


def upsert_heart_rate(profile_id: str, bpm: int, timestamp: datetime | None) -> HeartRateReading:
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
            (profile_id, bpm, reading_time.isoformat()),
        )
    return HeartRateReading(
        profile_id=profile_id,
        bpm=bpm,
        timestamp=reading_time,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def get_latest_heart_rate(profile_id: str) -> HeartRateReading:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT profile_id, bpm, timestamp FROM heart_rate_cache WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
    if row is None:
        return HeartRateReading(profile_id=profile_id, status=HeartRateStatus.unavailable)

    timestamp = datetime.fromisoformat(row["timestamp"])
    age_sec = _age_seconds(timestamp)
    return HeartRateReading(
        profile_id=profile_id,
        bpm=row["bpm"],
        timestamp=timestamp,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )
