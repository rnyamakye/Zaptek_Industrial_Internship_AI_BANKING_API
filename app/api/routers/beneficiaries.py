"""Beneficiaries router. Owner: Reginald."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.database import get_db
from app.schemas.beneficiaries import (
    BeneficiaryCreate,
    BeneficiaryResponse,
)
from app.services.beneficiary_service import (
    create_beneficiary,
    delete_beneficiary,
    get_beneficiaries,
)

router = APIRouter(
    prefix="/beneficiaries",
    tags=["Beneficiaries"],
)


@router.post(
    "",
    response_model=BeneficiaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: BeneficiaryCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    return create_beneficiary(
        db=db,
        customer_id=user.profile.id,
        data=data,
    )


@router.get(
    "",
    response_model=list[BeneficiaryResponse],
)
def list_beneficiaries(
    user: CurrentUser,
    response: Response,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    limit = min(limit, 100)

    beneficiaries, total = get_beneficiaries(
        db=db,
        customer_id=user.profile.id,
        skip=skip,
        limit=limit,
    )

    response.headers["X-Total-Count"] = str(total)

    return beneficiaries


@router.delete(
    "/{beneficiary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove(
    beneficiary_id: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    delete_beneficiary(
        db=db,
        customer_id=user.profile.id,
        beneficiary_id=beneficiary_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)