from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import LoanStatus


class LoanCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("100000"), decimal_places=2, description="GHS, max 100,000")
    duration: int = Field(ge=1, le=60, description="Months, 1 to 60")


class LoanDecision(BaseModel):
    status: Literal["APPROVED", "REJECTED"]


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    amount: Decimal
    interest_rate: Decimal
    duration: int
    status: LoanStatus
    created_at: datetime

    @computed_field
    @property
    def monthly_payment(self) -> Decimal:
        """Standard amortised payment (derived from amount, annual rate and duration)."""
        r = self.interest_rate / Decimal(1200)
        n = self.duration
        pay = self.amount / n if r == 0 else self.amount * r / (1 - (1 + r) ** -n)
        return pay.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
