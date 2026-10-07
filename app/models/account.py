from decimal import Decimal
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import AccountType, AccountStatus
from app.models.customer_profile import CustomerProfile
from app.models.transaction import Transaction
from app.models.transfer import Transfer


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True
    )
    account_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, native_enum=False, length=20)
    )
    currency: Mapped[str] = mapped_column(String(3), default="GHS")
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"))
    status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus, native_enum=False, length=20), default=AccountStatus.ACTIVE
    )

    customer: Mapped["CustomerProfile"] = relationship(
        back_populates="accounts")
    transactions: Mapped[list["Transaction"]
                         ] = relationship(back_populates="account")
    outgoing_transfers: Mapped[list["Transfer"]] = relationship(
        back_populates="sender_account")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
    )
