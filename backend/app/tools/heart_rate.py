from app.models import HeartRateReading
from app.logging_setup import get_logger
from app.tools.providers import get_heart_rate_provider

logger = get_logger("pulseagent.tools.heart_rate")


def execute_get_heart_rate(role_id: str) -> HeartRateReading:
    reading = get_heart_rate_provider().get_latest(role_id)
    logger.info(
        "heart-rate tool role_id=%s app_user_id=%s status=%s bpm=%s",
        role_id,
        reading.app_user_id,
        reading.status.value,
        reading.bpm,
    )
    return reading
