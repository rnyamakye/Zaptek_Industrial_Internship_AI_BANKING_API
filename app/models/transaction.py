from decimal import Decimal
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import TransactionType, TransactionStatus

class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, native_enum=False, length=20)
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, native_enum=False, length=20),
        default=TransactionStatus.PENDING,
        index=True,
    )

    account: Mapped["Account"] = relationship(back_populates="transactions")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="transaction")

    __table_args__ = (
        Index("ix_transactions_account_id_created_at", "account_id", "created_at"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )