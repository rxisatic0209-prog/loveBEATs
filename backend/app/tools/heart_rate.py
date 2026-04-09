from app.models import HeartRateReading
from app.tools.providers import get_heart_rate_provider


def execute_get_heart_rate(role_id: str) -> HeartRateReading:
    return get_heart_rate_provider().get_latest(role_id)
