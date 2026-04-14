from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

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


def upsert_heart_rate(
    bpm: int,
    timestamp: datetime | None,
    source: str = "local_cache",
) -> HeartRateReading:
    reading_time = timestamp or datetime.now(timezone.utc)
    age_sec = _age_seconds(reading_time)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO heart_rate_cache (cache_key, bpm, timestamp, source)
            VALUES ('global', ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                bpm = excluded.bpm,
                timestamp = excluded.timestamp,
                source = excluded.source
            """,
            (bpm, reading_time.isoformat(), source),
        )
        conn.execute(
            """
            INSERT INTO heart_rate_events (bpm, timestamp, source, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (bpm, reading_time.isoformat(), source, datetime.now(timezone.utc).isoformat()),
        )
    return HeartRateReading(
        bpm=bpm,
        timestamp=reading_time,
        source=source,
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def get_latest_heart_rate() -> HeartRateReading:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cache_key, bpm, timestamp, source FROM heart_rate_cache WHERE cache_key = 'global'",
        ).fetchone()
    if row is None:
        return HeartRateReading(status=HeartRateStatus.unavailable)

    timestamp = datetime.fromisoformat(row["timestamp"])
    age_sec = _age_seconds(timestamp)
    return HeartRateReading(
        bpm=row["bpm"],
        timestamp=timestamp,
        source=row["source"],
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def append_role_heart_rate(
    role_id: str,
    bpm: int,
    timestamp: datetime | None,
    source: str = "manual_api",
) -> HeartRateReading:
    from app.memory.role_store import get_role_optional

    role = get_role_optional(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="role not found")

    reading_time = timestamp or datetime.now(timezone.utc)
    reading = upsert_heart_rate(bpm, reading_time, source=source)
    created_at = datetime.now(timezone.utc)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO role_heart_rate_latest (role_id, bpm, timestamp, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(role_id) DO UPDATE SET
                bpm = excluded.bpm,
                timestamp = excluded.timestamp,
                source = excluded.source
            """,
            (role_id, bpm, reading_time.isoformat(), source),
        )
        conn.execute(
            """
            INSERT INTO role_heart_rate_events (role_id, bpm, timestamp, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (role_id, bpm, reading_time.isoformat(), source, created_at.isoformat()),
        )
    return reading.model_copy(update={"role_id": role_id})


def get_latest_role_heart_rate(role_id: str) -> HeartRateReading:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT bpm, timestamp, source FROM role_heart_rate_latest WHERE role_id = ?",
            (role_id,),
        ).fetchone()
    if row is None:
        return HeartRateReading(role_id=role_id, status=HeartRateStatus.unavailable)
    timestamp = datetime.fromisoformat(row["timestamp"])
    age_sec = _age_seconds(timestamp)
    return HeartRateReading(
        role_id=role_id,
        bpm=row["bpm"],
        timestamp=timestamp,
        source=row["source"],
        age_sec=age_sec,
        status=classify_heart_rate_status(age_sec),
    )


def list_role_heart_rate_events(role_id: str) -> list[HeartRateReading]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT bpm, timestamp, source
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
                bpm=row["bpm"],
                timestamp=timestamp,
                source=row["source"],
                age_sec=age_sec,
                status=classify_heart_rate_status(age_sec),
            )
        )
    return readings


def list_heart_rate_events() -> list[HeartRateReading]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT bpm, timestamp, source
            FROM heart_rate_events
            ORDER BY id ASC
            """
        ).fetchall()
    readings: list[HeartRateReading] = []
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        age_sec = _age_seconds(timestamp)
        readings.append(
            HeartRateReading(
                bpm=row["bpm"],
                timestamp=timestamp,
                source=row["source"],
                age_sec=age_sec,
                status=classify_heart_rate_status(age_sec),
            )
        )
    return readings


def delete_role_heart_rate_events(role_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM role_heart_rate_events WHERE role_id = ?", (role_id,))
        conn.execute("DELETE FROM role_heart_rate_latest WHERE role_id = ?", (role_id,))
