from datetime import date
from sqlalchemy import String, ForeignKey, CheckConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.enums import CardType, CardStatus

class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True
    )
    card_type: Mapped[CardType] = mapped_column(SAEnum(CardType, native_enum=False, length=20))
    last_four_digits: Mapped[str] = mapped_column(String(4))
    expiry_date: Mapped[date]
    status: Mapped[CardStatus] = mapped_column(
        SAEnum(CardStatus, native_enum=False, length=20), default=CardStatus.ACTIVE
    )

    customer: Mapped["CustomerProfile"] = relationship(back_populates="cards")

    __table_args__ = (
        CheckConstraint("length(last_four_digits) = 4", name="last_four_length"),
    )