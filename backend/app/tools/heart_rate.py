from app.models import HeartRateReading
from app.logging_setup import get_logger
from app.tools.providers import get_heart_rate_provider

logger = get_logger("LoveBeats.tools.heart_rate")


def execute_get_heart_rate(role_id: str) -> HeartRateReading:
    reading = get_heart_rate_provider().get_latest(role_id)
    logger.info(
        "heart-rate tool role_id=%s source=%s status=%s bpm=%s",
        role_id,
        reading.source,
        reading.status.value,
        reading.bpm,
    )
    return reading
