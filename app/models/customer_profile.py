from datetime import date
from typing import Optional
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.enums import VerificationStatus

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    date_of_birth: Mapped[date]
    address: Mapped[str] = mapped_column(String(255))
    occupation: Mapped[Optional[str]] = mapped_column(String(100))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False, length=20),
        default=VerificationStatus.PENDING,
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")
    beneficiaries: Mapped[list["Beneficiary"]] = relationship(back_populates="customer")
    cards: Mapped[list["Card"]] = relationship(back_populates="customer")
    loans: Mapped[list["Loan"]] = relationship(back_populates="customer")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="customer")