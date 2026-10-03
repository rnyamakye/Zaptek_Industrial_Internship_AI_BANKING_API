"""Accounts API router. Owner: Banasco."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, ensure_customer_access, is_staff, not_found
from app.db.database import get_db
from app.models.enums import AccountStatus
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.account_service import (
    create_account,
    get_account,
    list_accounts,
    update_account,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account_endpoint(
    data: AccountCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    if user.profile is None:
        raise not_found()

    return create_account(
        db,
        customer_id=user.profile.id,
        data=data,
    )


@router.get("", response_model=list[AccountResponse])
def get_accounts(
    user: CurrentUser,
    response: Response,
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    customer_id = None if is_staff(user) else user.profile.id

    accounts, total = list_accounts(
        db,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )

    response.headers["X-Total-Count"] = str(total)

    return accounts


@router.get("/{account_id}", response_model=AccountResponse)
def get_account_by_id(
    account_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    account = get_account(db, account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    return account


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account_by_id(
    account_id: int,
    data: AccountUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    account = get_account(db, account_id)

    if account is None:
        raise not_found()

    ensure_customer_access(user, account.customer_id)

    if not is_staff(user):
        # Customers can only close their own account (and only when empty).
        # Freezing/unfreezing is a staff decision, otherwise a customer could unfreeze
        # an account that staff froze.
        if data.status != AccountStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers can only close their account; ask staff to change other statuses",
            )
        if account.status == AccountStatus.CLOSED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is already closed")
        if account.status == AccountStatus.FROZEN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is frozen; contact staff")
        if account.balance != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Withdraw the remaining balance before closing")

    return update_account(db, account, data)