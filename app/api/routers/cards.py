"""Cards router. Customers request cards; only the last four digits are ever stored."""
import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentProfile, CurrentUser, ensure_customer_access, is_staff, not_found
from app.db.database import get_db
from app.models import Card
from app.models.enums import CardStatus
from app.schemas.card import CardCreate, CardResponse, CardUpdate

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED, summary="Request a card (customers only)")
def request_card(data: CardCreate, profile: CurrentProfile, db: Session = Depends(get_db)):
    today = date.today()
    card = Card(
        customer_id=profile.id,
        card_type=data.card_type,
        last_four_digits=f"{secrets.randbelow(10000):04d}",
        expiry_date=date(today.year + 4, today.month, 1),
        status=CardStatus.ACTIVE,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("", response_model=list[CardResponse], summary="List cards (own; staff see all)")
def list_cards(
    user: CurrentUser,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Card)
    if not is_staff(user):
        if user.profile is None:
            raise not_found()
        query = query.where(Card.customer_id == user.profile.id)
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    return db.scalars(query.order_by(Card.id.desc()).offset(skip).limit(limit)).all()


@router.patch("/{card_id}", response_model=CardResponse, summary="Block a card (customer) or change status (staff)")
def update_card(card_id: int, data: CardUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)
    if card is None:
        raise not_found()
    ensure_customer_access(user, card.customer_id)
    if not is_staff(user) and data.status != CardStatus.BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customers can only block their card; ask staff to unblock")
    card.status = data.status
    db.commit()
    db.refresh(card)
    return card
