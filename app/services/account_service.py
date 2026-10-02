from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.enums import AccountStatus
from app.schemas.account import AccountCreate, AccountUpdate


def generate_account_number(db: Session) -> str:
    last_account = db.execute(
        select(Account)
        .order_by(Account.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    next_id = 1 if last_account is None else last_account.id + 1
    return f"1000{next_id:06d}"


def create_account(
    db: Session,
    customer_id: int,
    data: AccountCreate,
) -> Account:
    account_number = generate_account_number(db)

    account = Account(
        customer_id=customer_id,
        account_number=account_number,
        account_type=data.account_type,
        currency=data.currency.upper(),
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return account


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

    count_query = select(Account.id)

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
    total = len(db.execute(count_query).scalars().all())

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