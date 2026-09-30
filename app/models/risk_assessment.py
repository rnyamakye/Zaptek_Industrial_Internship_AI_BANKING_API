from typing import Optional
from sqlalchemy import String, Float, ForeignKey, CheckConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import RiskLevel

class RiskAssessment(TimestampMixin, Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="RESTRICT"), index=True
    )
    transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), index=True
    )
    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, native_enum=False, length=20), index=True
    )
    model_version: Mapped[str] = mapped_column(String(20))

    customer: Mapped["CustomerProfile"] = relationship(back_populates="risk_assessments")
    transaction: Mapped[Optional["Transaction"]] = relationship(back_populates="risk_assessments")

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="risk_score_range"),
    )