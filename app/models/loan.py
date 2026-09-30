from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, CheckConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import LoanStatus

class Loan(TimestampMixin, Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # percent per year, e.g. 24.50
    duration: Mapped[int]  # months
    status: Mapped[LoanStatus] = mapped_column(
        SAEnum(LoanStatus, native_enum=False, length=20), default=LoanStatus.PENDING
    )

    customer: Mapped["CustomerProfile"] = relationship(back_populates="loans")

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("duration > 0", name="duration_positive"),
    )