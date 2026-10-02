from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.beneficiary import Beneficiary
from app.models.enums import AccountStatus, BeneficiaryStatus, TransferStatus
from app.models.transfer import Transfer
from app.schemas.transfer import TransferCreate


def create_transfer(
    db: Session,
    data: TransferCreate,
) -> Transfer:
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

        beneficiary = db.execute(
            select(Beneficiary)
            .where(Beneficiary.id == data.beneficiary_id)
        ).scalar_one_or_none()

        if beneficiary is None:
            raise ValueError("Beneficiary not found")

        if beneficiary.status != BeneficiaryStatus.ACTIVE:
            raise ValueError("Beneficiary is not active")

        amount = Decimal(data.amount)

        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero")

        if sender_account.balance < amount:
            raise ValueError("Insufficient account balance")

        sender_account.balance -= amount

        transfer = Transfer(
            sender_account_id=sender_account.id,
            beneficiary_id=beneficiary.id,
            amount=amount,
            reference=data.reference,
            status=TransferStatus.COMPLETED,
        )

        db.add(transfer)

        # Atomic commit:
        # balance deduction + transfer creation happen together.
        db.commit()
        db.refresh(transfer)

        return transfer

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