from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.loan import Loan
from app.models.enums import LoanStatus
from app.schemas.loans import LoanCreate


def create_loan(
    db: Session,
    customer_id: int,
    data: LoanCreate,
) -> Loan:

    loan = Loan(
        customer_id=customer_id,
        amount=data.amount,
        interest_rate=data.interest_rate,
        duration=data.duration,
        status=LoanStatus.PENDING,
    )

    db.add(loan)
    db.commit()
    db.refresh(loan)

    return loan


def get_loans(
    db: Session,
    customer_id: int,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Loan], int]:

    query = (
        select(Loan)
        .where(Loan.customer_id == customer_id)
        .order_by(Loan.id.desc())
    )

    total = len(db.scalars(query).all())

    loans = db.scalars(
        query.offset(skip).limit(limit)
    ).all()

    return loans, total


def get_loan(
    db: Session,
    customer_id: int,
    loan_id: int,
) -> Loan:

    loan = db.get(Loan, loan_id)

    if loan is None or loan.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loan not found",
        )

    return loan
