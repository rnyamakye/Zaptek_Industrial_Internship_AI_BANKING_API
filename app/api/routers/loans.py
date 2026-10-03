"""Loans router. Owner: Reginald (written during the final push).

Customers apply (status PENDING, interest rate set by the bank, never by the client).
STAFF/ADMIN approve or reject. The customer is notified.
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentProfile, CurrentUser, StaffUser, ensure_customer_access, is_staff, not_found
from app.core.audit import audit
from app.db.database import get_db
from app.models import Loan
from app.models.enums import LoanStatus, NotificationType
from app.schemas.loans import LoanCreate, LoanDecision, LoanResponse
from app.services.notification_service import notify

router = APIRouter(prefix="/loans", tags=["Loans"])


def interest_rate_for(duration_months: int) -> Decimal:
    """Annual interest rate (%) chosen by the bank from the loan length."""
    if duration_months <= 12:
        return Decimal("24.00")
    if duration_months <= 36:
        return Decimal("27.00")
    return Decimal("30.00")


@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for a loan (customers only)",
    responses={409: {"description": "A loan application is already pending"}},
)
def apply_for_loan(data: LoanCreate, profile: CurrentProfile, db: Session = Depends(get_db)):
    pending = db.scalar(
        select(func.count(Loan.id)).where(Loan.customer_id == profile.id, Loan.status == LoanStatus.PENDING)
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a pending loan application")
    loan = Loan(
        customer_id=profile.id,
        amount=data.amount,
        duration=data.duration,
        interest_rate=interest_rate_for(data.duration),
        status=LoanStatus.PENDING,
    )
    db.add(loan)
    notify(db, profile.user_id, NotificationType.LOAN, "Loan application received",
           f"Your application for GHS {data.amount} over {data.duration} months is pending review.")
    db.commit()
    db.refresh(loan)
    audit("loan_applied", loan_id=loan.id, customer_id=profile.id)
    return loan


@router.get("", response_model=list[LoanResponse], summary="List loans (own; staff see all)")
def list_loans(
    user: CurrentUser,
    response: Response,
    status_: Optional[LoanStatus] = Query(default=None, alias="status"),
    customer_id: Optional[int] = Query(default=None, ge=1, description="Staff only filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Loan)
    if is_staff(user):
        if customer_id:
            query = query.where(Loan.customer_id == customer_id)
    else:
        if user.profile is None:
            raise not_found()
        query = query.where(Loan.customer_id == user.profile.id)
    if status_:
        query = query.where(Loan.status == status_)
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    return db.scalars(query.order_by(Loan.id.desc()).offset(skip).limit(limit)).all()


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(loan_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise not_found()
    ensure_customer_access(user, loan.customer_id)
    return loan


@router.patch(
    "/{loan_id}",
    response_model=LoanResponse,
    summary="Approve or reject a pending loan (STAFF/ADMIN)",
    responses={400: {"description": "Loan is not pending"}},
)
def decide_loan(loan_id: int, data: LoanDecision, staff: StaffUser, db: Session = Depends(get_db)):
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise not_found()
    if loan.status != LoanStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending loans can be decided")
    loan.status = LoanStatus(data.status)
    notify(db, loan.customer.user_id, NotificationType.LOAN, f"Loan {data.status.lower()}",
           f"Your loan application of GHS {loan.amount} has been {data.status.lower()}.")
    db.commit()
    db.refresh(loan)
    audit("loan_decided", loan_id=loan.id, staff_id=staff.id, decision=data.status)
    return loan
