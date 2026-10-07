
from functools import lru_cache

from app.core.config import get_settings
from app.services.ai_risk_service import RiskModel, load_model


@lru_cache(maxsize=1)
def get_model() -> RiskModel:
    """Load once per process and reuse (loading is much slower than a prediction)."""
    settings = get_settings()
    return load_model(settings.risk_model_path, settings.risk_model_mode)
