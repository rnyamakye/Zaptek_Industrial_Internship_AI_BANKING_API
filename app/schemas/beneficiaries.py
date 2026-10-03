import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BeneficiaryStatus


class BeneficiaryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    account_number: str = Field(description="6 to 20 digits")
    bank_name: str = Field(min_length=2, max_length=100)

    @field_validator("name", "bank_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("account_number")
    @classmethod
    def _digits(cls, v: str) -> str:
        v = v.replace(" ", "")
        if not re.fullmatch(r"\d{6,20}", v):
            raise ValueError("Account number must be 6 to 20 digits")
        return v


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    name: str
    account_number: str
    bank_name: str
    status: BeneficiaryStatus
