from decimal import Decimal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TransferStatus


class TransferCreate(BaseModel):
    sender_account_id: int
    beneficiary_id: int
    amount: Decimal = Field(gt=0)
    reference: str = Field(min_length=1, max_length=64)


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_account_id: int
    beneficiary_id: int
    amount: Decimal
    reference: str
    status: TransferStatus
    created_at: datetime


class TransferRisk(BaseModel):
    risk_score: float
    risk_level: str
    model_version: str


class TransferWithRiskResponse(TransferResponse):
    """Returned by POST /transfers: the banking record plus the AI assessment (model output)."""

    risk: TransferRisk
