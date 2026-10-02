from pydantic import BaseModel, ConfigDict, Field
from app.core.pagination import pagination_params

class BeneficiaryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_number: str = Field(min_length=1, max_length=20)
    bank_name: str = Field(min_length=1, max_length=100)


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    name: str
    account_number: str
    bank_name: str
    status: str