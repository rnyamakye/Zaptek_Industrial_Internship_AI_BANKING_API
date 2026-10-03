from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import CardStatus, CardType


class CardCreate(BaseModel):
    card_type: CardType


class CardUpdate(BaseModel):
    status: CardStatus


class CardResponse(BaseModel):
    """Only the last four digits are ever stored or returned."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    card_type: CardType
    last_four_digits: str
    expiry_date: date
    status: CardStatus
