# """Transfers router. Owner: Banasco. Implement the endpoints listed in docs/ENDPOINTS.md."""
# from fastapi import APIRouter

# router = APIRouter(prefix="/transfers", tags=["Transfers"])

"""Transfers router. Owner: Banasco."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, ensure_customer_access, not_found
from app.db.database import get_db
from app.models.account import Account
from app.schemas.transfer import TransferCreate, TransferResponse
from app.services.transfer_service import (
    create_transfer,
    get_transfer,
    list_transfers,
)

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transfer_endpoint(
    data: TransferCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    account = db.get(Account, data.sender_account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    try:
        return create_transfer(db, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("", response_model=list[TransferResponse])
def get_transfers(
    user: CurrentUser,
    response: Response,
    account_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    account = db.get(Account, account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    transfers, total = list_transfers(
        db,
        sender_account_id=account_id,
        skip=skip,
        limit=limit,
    )

    response.headers["X-Total-Count"] = str(total)

    return transfers


@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer_by_id(
    transfer_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    transfer = get_transfer(db, transfer_id)

    if transfer is None:
        raise not_found()

    account = db.get(Account, transfer.sender_account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    return transfer