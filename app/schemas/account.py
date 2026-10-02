from decimal import Decimal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AccountStatus, AccountType


class AccountCreate(BaseModel):
    account_type: AccountType
    currency: str = Field(default="GHS", min_length=3, max_length=3)


class AccountUpdate(BaseModel):
    status: AccountStatus


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    account_number: str
    account_type: AccountType
    currency: str
    balance: Decimal
    status: AccountStatus
    created_at: datetime