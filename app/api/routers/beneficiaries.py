"""Beneficiaries router. Owner: Reginald (written during the final push)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentProfile, CurrentUser, ensure_customer_access, is_staff, not_found
from app.db.database import get_db
from app.models import Beneficiary
from app.models.enums import BeneficiaryStatus
from app.schemas.beneficiaries import BeneficiaryCreate, BeneficiaryResponse

router = APIRouter(prefix="/beneficiaries", tags=["Beneficiaries"])


@router.post(
    "",
    response_model=BeneficiaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a beneficiary (customers only)",
    responses={409: {"description": "Beneficiary already saved"}},
)
def create_beneficiary(data: BeneficiaryCreate, profile: CurrentProfile, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(Beneficiary).where(
            Beneficiary.customer_id == profile.id,
            Beneficiary.account_number == data.account_number,
            Beneficiary.bank_name == data.bank_name,
        )
    )
    if existing:
        if existing.status == BeneficiaryStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Beneficiary already saved")
        # previously removed: bring it back (transfers history keeps pointing at the same row)
        existing.status = BeneficiaryStatus.ACTIVE
        existing.name = data.name
        db.commit()
        db.refresh(existing)
        return existing
    beneficiary = Beneficiary(customer_id=profile.id, **data.model_dump())
    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)
    return beneficiary


@router.get("", response_model=list[BeneficiaryResponse], summary="List beneficiaries (own; staff see all)")
def list_beneficiaries(
    user: CurrentUser,
    response: Response,
    status_: Optional[BeneficiaryStatus] = Query(default=BeneficiaryStatus.ACTIVE, alias="status"),
    customer_id: Optional[int] = Query(default=None, ge=1, description="Staff only filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Beneficiary)
    if is_staff(user):
        if customer_id:
            query = query.where(Beneficiary.customer_id == customer_id)
    else:
        if user.profile is None:
            raise not_found()
        query = query.where(Beneficiary.customer_id == user.profile.id)
    if status_:
        query = query.where(Beneficiary.status == status_)
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    return db.scalars(query.order_by(Beneficiary.id.desc()).offset(skip).limit(limit)).all()


@router.delete(
    "/{beneficiary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a beneficiary (soft delete: transfer history is kept)",
)
def delete_beneficiary(beneficiary_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    beneficiary = db.get(Beneficiary, beneficiary_id)
    if beneficiary is None:
        raise not_found()
    ensure_customer_access(user, beneficiary.customer_id)
    if beneficiary.status != BeneficiaryStatus.INACTIVE:
        beneficiary.status = BeneficiaryStatus.INACTIVE
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
