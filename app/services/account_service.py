import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.enums import AccountStatus
from app.schemas.account import AccountCreate, AccountUpdate


def generate_account_number(db: Session) -> str:
    """10 digits starting with 1000, random tail, checked for uniqueness."""
    for _ in range(10):
        candidate = f"1000{secrets.randbelow(10**6):06d}"
        if db.scalar(select(Account.id).where(Account.account_number == candidate)) is None:
            return candidate
    raise RuntimeError("Could not generate a unique account number")


def create_account(
    db: Session,
    customer_id: int,
    data: AccountCreate,
) -> Account:
    for _ in range(5):  # retry if two requests picked the same number at the same moment
        account = Account(
            customer_id=customer_id,
            account_number=generate_account_number(db),
            account_type=data.account_type,
            currency=data.currency.upper(),
        )
        db.add(account)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(account)
        return account
    raise RuntimeError("Could not create account")


def get_account(
    db: Session,
    account_id: int,
) -> Account | None:
    return db.execute(
        select(Account).where(Account.id == account_id)
    ).scalar_one_or_none()


def list_accounts(
    db: Session,
    customer_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Account], int]:
    query = select(Account)

    count_query = select(func.count(Account.id))

    if customer_id is not None:
        query = query.where(Account.customer_id == customer_id)
        count_query = count_query.where(Account.customer_id == customer_id)

    query = (
        query
        .order_by(Account.id.desc())
        .offset(skip)
        .limit(limit)
    )

    accounts = list(db.execute(query).scalars().all())
    total = db.execute(count_query).scalar_one()

    return accounts, total


def update_account(
    db: Session,
    account: Account,
    data: AccountUpdate,
) -> Account:
    account.status = data.status

    db.commit()
    db.refresh(account)

    return account