"""Loans router. Owner: Reginald."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.schemas.loans import LoanCreate, LoanResponse
from app.services.loan_services import (
    create_loan,
    get_loan,
    get_loans,
)
from app.core.pagination import pagination_params



router = APIRouter(
    prefix="/loans",
    tags=["Loans"],
)


@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: LoanCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    return create_loan(
        db=db,
        customer_id=user.profile.id,
        data=data,
    )


@router.get(
    "",
    response_model=list[LoanResponse],
)
def list_loans(
    user: CurrentUser,
    response: Response,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    limit = min(limit, 100)

    loans, total = get_loans(
        db=db,
        customer_id=user.profile.id,
        skip=skip,
        limit=limit,
    )

    response.headers["X-Total-Count"] = str(total)

    return loans


@router.get(
    "/{loan_id}",
    response_model=LoanResponse,
)
def get_one(
    loan_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    return get_loan(
        db=db,
        customer_id=user.profile.id,
        loan_id=loan_id,
    )