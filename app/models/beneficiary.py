from sqlalchemy import String, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.enums import BeneficiaryStatus

class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    account_number: Mapped[str] = mapped_column(String(20))
    bank_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[BeneficiaryStatus] = mapped_column(
        SAEnum(BeneficiaryStatus, native_enum=False, length=20),
        default=BeneficiaryStatus.ACTIVE,
    )

    customer: Mapped["CustomerProfile"] = relationship(back_populates="beneficiaries")
    transfers: Mapped[list["Transfer"]] = relationship(back_populates="beneficiary")

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "account_number", "bank_name",
            name="uq_beneficiaries_customer_account_bank",
        ),
    )