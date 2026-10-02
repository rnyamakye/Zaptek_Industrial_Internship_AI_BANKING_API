"""Transactions API router. Owner: Banasco."""
# from fastapi import HTTPException
# from sqlalchemy import func, select
# from app.models.transaction import Transaction

# from fastapi import APIRouter, Depends, Query, Response, status
# from sqlalchemy.orm import Session
# from app.models.account import Account

# from app.api.deps import CurrentUser, ensure_customer_access, is_staff, not_found
# from app.db.database import get_db

# from app.schemas.transaction import (
#     TransactionCreate,
#     TransactionResponse,
   
# )
# from app.services.transaction_service import (
#     create_transaction,
#     get_transaction,
#     list_transactions,
# )

# 



from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, ensure_customer_access, is_staff, not_found
from app.db.database import get_db
from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services.transaction_service import (
    create_transaction,
    get_transaction,
    list_transactions,
)


router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction_endpoint(
    data: TransactionCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    account = db.get(Account, data.account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    try:
        transaction, _risk_result = create_transaction(db, data)
        return transaction
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("", response_model=list[TransactionResponse])
def get_transactions(
    user: CurrentUser,
    response: Response,
    db: Session = Depends(get_db),
    account_id: int | None = Query(default=None, ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    if account_id is not None:
        account = db.get(Account, account_id)

        if account is None:
            raise not_found()

        ensure_customer_access(user, account.customer_id)

        transactions, total = list_transactions(
            db,
            account_id=account_id,
            skip=skip,
            limit=limit,
        )
    else:
        if not is_staff(user):
            raise not_found()

        query = (
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        transactions = list(db.execute(query).scalars().all())

        total = db.execute(
            select(func.count(Transaction.id))
        ).scalar_one()

    response.headers["X-Total-Count"] = str(total)

    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction_by_id(
    transaction_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    transaction = get_transaction(db, transaction_id)

    if transaction is None:
        raise not_found()

    ensure_customer_access(user, transaction.account.customer_id)

    return transaction
