"""AI router. Everything here is MODEL-GENERATED output, clearly separate from banking records.

- GET /ai/customers/{customer_id}/insights   rule-based customer insights
- GET /ai/transactions/{transaction_id}/risk the stored risk assessment of a transaction
- GET /ai/model/info                         risk model version/kind (STAFF/ADMIN)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, StaffUser, ensure_customer_access, not_found
from app.db.database import get_db
from app.models import CustomerProfile, RiskAssessment
from app.schemas.ai import CustomerInsights, ModelInfo, RiskAssessmentResponse
from app.services.ai_risk_service import FEATURE_NAMES, LOW_MAX, MEDIUM_MAX, HybridRiskModel, RuleBasedRiskModel
from app.services.insights_service import build_insights
from app.services.transaction_service import risk_service

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get(
    "/customers/{customer_id}/insights",
    response_model=CustomerInsights,
    summary="AI insights for a customer (model-generated)",
)
def customer_insights(customer_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """`customer_id` is the customer profile id. Customers can only request their own."""
    if db.get(CustomerProfile, customer_id) is None:
        raise not_found()
    ensure_customer_access(user, customer_id)
    return build_insights(db, customer_id)


@router.get(
    "/transactions/{transaction_id}/risk",
    response_model=RiskAssessmentResponse,
    summary="Stored AI risk assessment for a transaction",
)
def transaction_risk(transaction_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    assessment = db.scalar(select(RiskAssessment).where(
        RiskAssessment.transaction_id == transaction_id))
    if assessment is None:
        raise not_found()
    ensure_customer_access(user, assessment.customer_id)
    return RiskAssessmentResponse(
        transaction_id=assessment.transaction_id,
        customer_id=assessment.customer_id,
        risk_score=float(assessment.risk_score),
        risk_level=assessment.risk_level.value,
        model_version=assessment.model_version,
        created_at=assessment.created_at,
    )


@router.get("/model/info", response_model=ModelInfo, summary="Risk model version and thresholds (STAFF/ADMIN)")
def model_info(_: StaffUser):
    model = risk_service._model
    if isinstance(model, RuleBasedRiskModel):
        kind = "rule-based"
    elif isinstance(model, HybridRiskModel):
        kind = "hybrid"  # max(ML score, rule score)
    else:
        kind = "ml"
    return ModelInfo(
        model_version=risk_service.model_version,
        model_kind=kind,
        feature_names=FEATURE_NAMES,
        thresholds={"low_max": LOW_MAX, "medium_max": MEDIUM_MAX},
    )
