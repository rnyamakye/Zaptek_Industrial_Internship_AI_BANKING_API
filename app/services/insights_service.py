"""Customer insights (MODEL-GENERATED, rule-based v1).

Deterministic rules over the last 30 days of activity. The output is advisory text; the
banking records it is based on (accounts, transactions, transfers) are never modified.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, RiskAssessment, Transaction, Transfer
from app.models.enums import RiskLevel, TransactionStatus, TransactionType
from app.schemas.ai import CustomerInsights, InsightDetail

INSIGHTS_VERSION = "rules-insights-1.0"
WINDOW_DAYS = 30

CREDITS = (TransactionType.DEPOSIT, TransactionType.CREDIT)
DEBITS = (TransactionType.WITHDRAWAL, TransactionType.DEBIT)


def build_insights(db: Session, customer_id: int) -> CustomerInsights:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)
    last_day = now - timedelta(hours=24)

    account_ids = select(Account.id).where(Account.customer_id == customer_id)
    in_window = (Transaction.account_id.in_(account_ids), Transaction.created_at >= since)

    count_30d, avg_amount, max_amount = db.execute(
        select(func.count(Transaction.id), func.avg(Transaction.amount), func.max(Transaction.amount)).where(*in_window)
    ).one()
    count_24h = db.scalar(
        select(func.count(Transaction.id)).where(Transaction.account_id.in_(account_ids), Transaction.created_at >= last_day)
    )
    credits_total = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(*in_window, Transaction.transaction_type.in_(CREDITS)))
    debits_total = db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(*in_window, Transaction.transaction_type.in_(DEBITS)))
    flagged = db.scalar(select(func.count(Transaction.id)).where(*in_window, Transaction.status == TransactionStatus.FLAGGED))
    high_risk = db.scalar(
        select(func.count(RiskAssessment.id)).where(
            RiskAssessment.customer_id == customer_id,
            RiskAssessment.created_at >= since,
            RiskAssessment.risk_level == RiskLevel.HIGH,
        )
    )
    transfer_count, transfer_total = db.execute(
        select(func.count(Transfer.id), func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.sender_account_id.in_(account_ids), Transfer.created_at >= since
        )
    ).one()

    details: list[InsightDetail] = []

    def add(code: str, severity: str, message: str) -> None:
        details.append(InsightDetail(code=code, severity=severity, message=message))

    if count_30d == 0 and transfer_count == 0:
        add("NO_ACTIVITY", "INFO", f"No activity in the last {WINDOW_DAYS} days")
    if count_24h >= 5:
        add("HIGH_FREQUENCY", "WARNING", f"High transaction frequency ({count_24h} transactions in the last 24 hours)")
    if count_30d >= 3 and avg_amount and max_amount and Decimal(max_amount) > Decimal(avg_amount) * 4:
        add("UNUSUAL_PATTERN", "WARNING", "Unusual transaction pattern detected (one amount is far above your average)")
    if high_risk:
        add("HIGH_RISK_ACTIVITY", "ALERT", f"{high_risk} high-risk transaction(s) detected in the last {WINDOW_DAYS} days")
    if flagged:
        add("FLAGGED_PENDING_REVIEW", "ALERT", f"{flagged} transaction(s) flagged for staff review")
    if Decimal(debits_total) > Decimal(credits_total) and Decimal(debits_total) > 0:
        add("SPENDING_EXCEEDS_INCOME", "INFO", "Money going out exceeds money coming in over this period")
    if transfer_count >= 5:
        add("FREQUENT_TRANSFERS", "INFO", f"{transfer_count} transfers sent in the last {WINDOW_DAYS} days")

    return CustomerInsights(
        customer_id=customer_id,
        insights=[d.message for d in details],
        details=details,
        window_days=WINDOW_DAYS,
        generated_at=now,
        generated_by=INSIGHTS_VERSION,
    )
