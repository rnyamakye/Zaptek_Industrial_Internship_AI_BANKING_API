from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.beneficiary import Beneficiary
from app.models.enums import (
    AccountStatus,
    BeneficiaryStatus,
    NotificationType,
    RiskLevel,
    TransferStatus,
)
from app.models.risk_assessment import RiskAssessment
from app.models.transfer import Transfer
from app.schemas.transfer import TransferCreate
from app.services.notification_service import notify
from app.services.transaction_service import DuplicateReferenceError, risk_service


def create_transfer(
    db: Session,
    data: TransferCreate,
) -> tuple[Transfer, object]:
    """
    Create a transfer and deduct the sender's balance atomically.

    If transfer creation fails after the balance update,
    the entire operation is rolled back.
    """

    try:
        sender_account = db.execute(
            select(Account)
            .where(Account.id == data.sender_account_id)
            .with_for_update()
        ).scalar_one_or_none()

        if sender_account is None:
            raise ValueError("Sender account not found")

        if sender_account.status != AccountStatus.ACTIVE:
            raise ValueError("Sender account is not active")

        if db.scalar(select(Transfer.id).where(Transfer.reference == data.reference)) is not None:
            raise DuplicateReferenceError("Reference already used")

        beneficiary = db.execute(
            select(Beneficiary)
            .where(Beneficiary.id == data.beneficiary_id)
        ).scalar_one_or_none()

        # A beneficiary can only be used by the customer who owns it (same message as
        # "unknown" so other customers' beneficiaries are not revealed).
        if beneficiary is None or beneficiary.customer_id != sender_account.customer_id:
            raise ValueError("Beneficiary not found")

        if beneficiary.status != BeneficiaryStatus.ACTIVE:
            raise ValueError("Beneficiary is not active")

        amount = Decimal(data.amount)

        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero")

        if sender_account.balance < amount:
            raise ValueError("Insufficient account balance")

        # AI risk assessment (statistics are taken BEFORE this transfer is added).
        now = datetime.now(timezone.utc)
        avg_amount = db.execute(
            select(func.avg(Transfer.amount)).where(
                Transfer.sender_account_id == sender_account.id,
                Transfer.status == TransferStatus.COMPLETED,
            )
        ).scalar()
        recent_count = db.execute(
            select(func.count(Transfer.id)).where(
                Transfer.sender_account_id == sender_account.id,
                Transfer.created_at >= now - timedelta(hours=1),
            )
        ).scalar_one()
        paid_before = db.execute(
            select(func.count(Transfer.id)).where(
                Transfer.beneficiary_id == beneficiary.id,
                Transfer.status.in_([TransferStatus.COMPLETED, TransferStatus.FLAGGED]),
            )
        ).scalar_one()
        risk_result = risk_service.assess(
            risk_service.prepare_features(
                amount=float(amount),
                avg_amount=float(avg_amount or 0),
                txn_count_last_hour=recent_count,
                hour_of_day=now.hour,
                is_new_beneficiary=paid_before == 0,
            )
        )

        sender_account.balance -= amount

        flagged = risk_result.risk_level == "HIGH"
        transfer = Transfer(
            sender_account_id=sender_account.id,
            beneficiary_id=beneficiary.id,
            amount=amount,
            reference=data.reference,
            # HIGH risk: funds are held and staff must review.
            status=TransferStatus.FLAGGED if flagged else TransferStatus.COMPLETED,
        )
        db.add(transfer)

        db.add(
            RiskAssessment(
                customer_id=sender_account.customer_id,
                transaction_id=None,  # transfers are not Transaction rows
                risk_score=risk_result.risk_score,
                risk_level=RiskLevel(risk_result.risk_level),
                model_version=risk_result.model_version,
            )
        )
        if flagged:
            notify(
                db,
                sender_account.customer.user_id,
                NotificationType.SECURITY,
                "Transfer flagged for review",
                f"Your transfer of {amount} to {beneficiary.name} (ref {data.reference}) "
                "was flagged as high risk and is awaiting staff review.",
            )

        # Atomic commit: balance deduction + transfer + risk assessment (+ notification).
        db.commit()
        db.refresh(transfer)

        return transfer, risk_result

    except IntegrityError as exc:
        db.rollback()
        raise DuplicateReferenceError("Reference already used") from exc
    except Exception:
        db.rollback()
        raise


def get_transfer(
    db: Session,
    transfer_id: int,
) -> Transfer | None:
    return db.execute(
        select(Transfer).where(Transfer.id == transfer_id)
    ).scalar_one_or_none()


def list_transfers(
    db: Session,
    sender_account_id: int,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Transfer], int]:
    query = (
        select(Transfer)
        .where(Transfer.sender_account_id == sender_account_id)
        .order_by(Transfer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    transfers = list(db.execute(query).scalars().all())

    total = db.execute(
        select(Transfer.id)
        .where(Transfer.sender_account_id == sender_account_id)
    ).scalars().all()

    return transfers, len(total)