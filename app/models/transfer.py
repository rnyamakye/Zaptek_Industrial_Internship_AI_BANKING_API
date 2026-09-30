from decimal import Decimal
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import TransferStatus

class Transfer(TimestampMixin, Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    beneficiary_id: Mapped[int] = mapped_column(
        ForeignKey("beneficiaries.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, native_enum=False, length=20),
        default=TransferStatus.PENDING,
        index=True,
    )

    sender_account: Mapped["Account"] = relationship(back_populates="outgoing_transfers")
    beneficiary: Mapped["Beneficiary"] = relationship(back_populates="transfers")

    __table_args__ = (
        Index("ix_transfers_sender_account_id_created_at", "sender_account_id", "created_at"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )