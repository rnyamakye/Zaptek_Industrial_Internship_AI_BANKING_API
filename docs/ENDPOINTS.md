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
- POST /accounts  (customer; body account_type, currency?) -> balance starts at 0
- GET /accounts  (own; staff see all; X-Total-Count)
- GET /accounts/{id}
- PATCH /accounts/{id}  body {status}. Customers: only CLOSED, and only an empty, non-frozen account. Staff: any status (freeze/unfreeze)

## Transactions (Banasco)
- POST /transactions  body account_id, transaction_type, amount, currency, reference (unique). Response = transaction + `risk` {transaction_id, risk_score, risk_level, model_version}
  - DEPOSIT / CREDIT: STAFF/ADMIN only (403 for customers). WITHDRAWAL / DEBIT: account owner.
  - 400 insufficient balance / inactive account / currency mismatch, 409 duplicate reference
  - HIGH risk -> status FLAGGED, customer gets a SECURITY notification
- GET /transactions?account_id=  (customers must pass account_id; staff may omit; X-Total-Count)
- GET /transactions/{id}

## Transfers (Banasco)
- POST /transfers  body sender_account_id, beneficiary_id (must belong to the account owner and be ACTIVE), amount, reference (unique). Response = transfer + `risk`
- GET /transfers?account_id=
- GET /transfers/{id}

## Beneficiaries (Reginald)
- POST /beneficiaries  body name, account_number (6-20 digits), bank_name. Re-adding a removed one restores it. 409 if already saved
- GET /beneficiaries?status=ACTIVE|INACTIVE&customer_id=(staff only)
- DELETE /beneficiaries/{id}  (soft delete: status INACTIVE, transfer history kept) -> 204

## Loans (Reginald)
- POST /loans  body amount (max 100,000), duration (1-60 months). Status is PENDING and the interest rate is set by the bank from the duration (24% up to 12 months, 27% up to 36, 30% above). One pending application at a time (409)
- GET /loans?status=&customer_id=(staff only)  /  GET /loans/{id}  (response includes `monthly_payment`)
- PATCH /loans/{id}  body {status: APPROVED|REJECTED}  (STAFF/ADMIN, pending loans only; customer is notified)

## Cards
- POST /cards  body card_type DEBIT|CREDIT (only the last four digits are stored)
- GET /cards
- PATCH /cards/{id}  body {status}. Customers can only BLOCK; staff can change any status

## Notifications
- GET /notifications?unread=true  (own only, newest first)
- PATCH /notifications/{id}/read

## AI (all output is model-generated and labelled)
- GET /ai/customers/{customer_id}/insights  (customer_id = customer profile id; own only, staff any). Response has `insights`, `details`, `is_model_generated`, `generated_by`, `disclaimer`
- GET /ai/transactions/{transaction_id}/risk  (stored risk assessment)
- GET /ai/model/info  (STAFF/ADMIN: model version, kind, features, thresholds)

## Health
- GET /health -> `{"status": "healthy", "service": "ai-banking-api", "version": "1.0.0"}`

## Decisions (all made)
- HIGH risk (score >= 0.70) transaction or transfer: status `FLAGGED`, funds held, customer notified, staff review. The model is never allowed to block on its own failure: it falls back to the rule-based model.
- Refresh tokens: DECIDED stateless JWT (no extra table). Cannot be revoked before expiry; suspended users are blocked because status is checked on every request and refresh.
- Roles: CUSTOMER, STAFF, ADMIN (DECIDED). First admin is created with `python -m app.db.create_admin <email> <password>`
