from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.beneficiary import Beneficiary
from app.models.enums import BeneficiaryStatus
from app.schemas.beneficiaries import BeneficiaryCreate


def create_beneficiary(
    db: Session,
    customer_id: int,
    data: BeneficiaryCreate,
) -> Beneficiary:
    beneficiary = Beneficiary(
        customer_id=customer_id,
        name=data.name,
        account_number=data.account_number,
        bank_name=data.bank_name,
        status=BeneficiaryStatus.ACTIVE,
    )

    db.add(beneficiary)

    try:
        db.commit()
        db.refresh(beneficiary)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Beneficiary already exists",
        )

    return beneficiary


def get_beneficiaries(
    db: Session,
    customer_id: int,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Beneficiary], int]:

    query = (
        select(Beneficiary)
        .where(Beneficiary.customer_id == customer_id)
        .order_by(Beneficiary.id.desc())
    )

    total = len(db.scalars(query).all())

    beneficiaries = db.scalars(
        query.offset(skip).limit(limit)
    ).all()

    return beneficiaries, total


def delete_beneficiary(
    db: Session,
    customer_id: int,
    beneficiary_id: int,
) -> None:

    beneficiary = db.get(Beneficiary, beneficiary_id)

    if beneficiary is None or beneficiary.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary not found",
        )

    beneficiary.status = BeneficiaryStatus.INACTIVE

    db.commit() 