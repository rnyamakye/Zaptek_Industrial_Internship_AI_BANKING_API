from decimal import Decimal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TransactionStatus, TransactionType


class TransactionCreate(BaseModel):
    account_id: int
    transaction_type: TransactionType
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    reference: str = Field(min_length=1, max_length=64)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    transaction_type: TransactionType
    amount: Decimal
    currency: str
    reference: str
    status: TransactionStatus
    created_at: datetime


class TransactionRiskResponse(BaseModel):
    transaction_id: int
    risk_score: float
    risk_level: str
    model_version: str