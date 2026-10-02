from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.enums import (
    AccountStatus,
    TransactionStatus,
    TransactionType,
)
from app.schemas.transaction import TransactionCreate
from app.services.ai_risk_service import AIRiskService


risk_service = AIRiskService()


CREDIT_TYPES = {
    TransactionType.DEPOSIT,
    TransactionType.CREDIT,
}

DEBIT_TYPES = {
    TransactionType.WITHDRAWAL,
    TransactionType.DEBIT,
}


def create_transaction(
    db: Session,
    data: TransactionCreate,
) -> tuple[Transaction, object]:
    """
    Create a transaction and update the account balance atomically.

    If anything fails, the database transaction is rolled back.
    """

    try:
        account = db.execute(
            select(Account)
            .where(Account.id == data.account_id)
            .with_for_update()
        ).scalar_one_or_none()

        if account is None:
            raise ValueError("Account not found")

        if account.status != AccountStatus.ACTIVE:
            raise ValueError("Account is not active")

        if account.currency.upper() != data.currency.upper():
            raise ValueError("Transaction currency does not match account currency")

        amount = Decimal(data.amount)

        if amount <= 0:
            raise ValueError("Transaction amount must be greater than zero")

        # Calculate statistics BEFORE adding the new transaction.
        avg_amount = db.execute(
            select(func.avg(Transaction.amount))
            .where(
                Transaction.account_id == account.id,
                Transaction.status == TransactionStatus.COMPLETED,
            )
        ).scalar()

        average_amount = float(avg_amount or 0)

        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        txn_count_last_hour = db.execute(
            select(func.count(Transaction.id))
            .where(
                Transaction.account_id == account.id,
                Transaction.created_at >= one_hour_ago,
            )
        ).scalar_one()

        features = risk_service.prepare_features(
            amount=float(amount),
            avg_amount=average_amount,
            txn_count_last_hour=txn_count_last_hour,
            hour_of_day=now.hour,
            is_new_beneficiary=False,
        )

        risk_result = risk_service.assess(features)

        # Apply balance change.
        if data.transaction_type in CREDIT_TYPES:
            account.balance += amount

        elif data.transaction_type in DEBIT_TYPES:
            if account.balance < amount:
                raise ValueError("Insufficient account balance")

            account.balance -= amount

        else:
            raise ValueError(
                f"Unsupported transaction type: {data.transaction_type}"
            )

        transaction_status = (
            TransactionStatus.FLAGGED
            if risk_result.risk_level == "HIGH"
            else TransactionStatus.COMPLETED
        )

        transaction = Transaction(
            account_id=account.id,
            transaction_type=data.transaction_type,
            amount=amount,
            currency=data.currency.upper(),
            reference=data.reference,
            status=transaction_status,
        )

        db.add(transaction)

        # One commit = atomic balance + transaction update.
        db.commit()
        db.refresh(transaction)

        return transaction, risk_result

    except Exception:
        db.rollback()
        raise


def get_transaction(
    db: Session,
    transaction_id: int,
) -> Transaction | None:
    return db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    ).scalar_one_or_none()


def list_transactions(
    db: Session,
    account_id: int,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Transaction], int]:
    query = (
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    transactions = list(db.execute(query).scalars().all())

    total = db.execute(
        select(func.count(Transaction.id))
        .where(Transaction.account_id == account_id)
    ).scalar_one()

    return transactions, total