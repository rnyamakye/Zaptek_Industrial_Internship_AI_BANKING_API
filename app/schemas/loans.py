from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LoanCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    interest_rate: Decimal = Field(ge=0)
    duration: int = Field(gt=0)


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    amount: Decimal
    interest_rate: Decimal
    duration: int
    status: str
    created_at: datetime