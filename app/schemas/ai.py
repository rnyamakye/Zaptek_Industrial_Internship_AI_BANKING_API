from datetime import datetime

from pydantic import BaseModel


class InsightDetail(BaseModel):
    code: str
    severity: str  # INFO | WARNING | ALERT
    message: str


class CustomerInsights(BaseModel):
    """MODEL-GENERATED output. Not a banking record: do not use it as a statement of account."""

    customer_id: int
    insights: list[str]
    details: list[InsightDetail]
    window_days: int
    generated_at: datetime
    generated_by: str
    is_model_generated: bool = True
    disclaimer: str = (
        "Insights are automatically generated from recent activity and may be inaccurate. "
        "They are not part of the official account records."
    )


class RiskAssessmentResponse(BaseModel):
    transaction_id: int
    customer_id: int
    risk_score: float
    risk_level: str
    model_version: str
    created_at: datetime
    is_model_generated: bool = True


class ModelInfo(BaseModel):
    model_version: str
    model_kind: str  # "rule-based" or "ml"
    feature_names: list[str]
    thresholds: dict[str, float]
