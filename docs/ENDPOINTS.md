# API contract (edit this BEFORE coding, then stick to it)

Base conventions (proposed):
- Auth: `Authorization: Bearer <access_token>`
- Pagination on list endpoints: `?skip=0&limit=20` (limit max 100), total in `X-Total-Count` header
- Errors: `{"detail": "message"}` with correct status codes (400, 401, 403, 404, 409, 422)
- Money as decimal strings or numbers with 2 dp; currency as ISO code (e.g. GHS)
- Never return `password_hash`

## Auth (Rick) - DONE, see "How to use auth in your router" below
- POST /auth/register  (JSON: full_name, email, phone, password, date_of_birth, address, occupation?) -> always role CUSTOMER, creates the customer profile too
- POST /auth/login  (form fields `username` = email, `password`) -> access_token, refresh_token
- POST /auth/refresh  (JSON: refresh_token) -> new token pair
- GET  /auth/me -> user + customer profile (profile is null for STAFF/ADMIN)

## Admin (Rick) - DONE
- GET /admin/users?role=&status=&skip=&limit=  (STAFF, ADMIN; total in X-Total-Count)
- GET /admin/users/{id}  (STAFF, ADMIN)
- PATCH /admin/users/{id}  body {role?, status?}  (ADMIN only; cannot change own account)

## How to use auth in your router
```python
from app.api.deps import CurrentUser, CurrentProfile, StaffUser, ensure_customer_access, not_found

@router.get("/{id}")
def get_thing(id: int, user: CurrentUser, db: Session = Depends(get_db)):
    thing = db.get(Thing, id)
    if thing is None:
        raise not_found()
    ensure_customer_access(user, thing.customer_id)   # 404 if it belongs to another customer
    return thing
```
- `CurrentUser`: any logged-in active user. `CurrentProfile`: the customer's profile (customers only). `StaffUser`: STAFF or ADMIN.
- `customer_id` everywhere means `customer_profiles.id`, NOT `users.id`. Use `user.profile.id` to get it.
- CUSTOMER sees only their own data; STAFF/ADMIN see everything. Other people's resources return 404, not 403.
- In tests use the `make_user(role=...)` and `auth_headers(user)` fixtures from `tests/conftest.py`.

## Accounts (Banasco)
- POST /accounts
- GET /accounts
- GET /accounts/{id}
- PATCH /accounts/{id}

## Transactions (Banasco)
- POST /transactions
- GET /transactions
- GET /transactions/{id}

## Transfers (Banasco)
- POST /transfers
- GET /transfers
- GET /transfers/{id}

## Beneficiaries (Reginald)
- POST /beneficiaries
- GET /beneficiaries
- DELETE /beneficiaries/{id}

## Loans (Reginald)
- POST /loans
- GET /loans
- GET /loans/{id}

## AI
- GET /ai/customers/{customer_id}/insights (Sakeenah)
- Risk assessment runs inside POST /transactions (Angela's service, Banasco's call). Response includes:
  `{"transaction_id": 1023, "risk_score": 0.87, "risk_level": "HIGH", "model_version": "1.0"}`

## Admin (Rick, STAFF/ADMIN only)
- To be agreed (for example GET /admin/users)

## Health
- GET /health -> `{"status": "healthy", "service": "ai-banking-api", "version": "1.0.0"}`

## Open decisions
- What does a HIGH risk transaction do? Proposal: status `FLAGGED` (already in the enums) for staff review, not blocked.
- Refresh tokens: DECIDED stateless JWT (no extra table). Cannot be revoked before expiry; suspended users are blocked because status is checked on every request and refresh.
- Roles: CUSTOMER, STAFF, ADMIN (DECIDED). First admin is created with `python -m app.db.create_admin <email> <password>`
