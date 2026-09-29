# API contract (edit this BEFORE coding, then stick to it)

Base conventions (proposed):
- Auth: `Authorization: Bearer <access_token>`
- Pagination on list endpoints: `?skip=0&limit=20` (limit max 100), total in `X-Total-Count` header
- Errors: `{"detail": "message"}` with correct status codes (400, 401, 403, 404, 409, 422)
- Money as decimal strings or numbers with 2 dp; currency as ISO code (e.g. GHS)
- Never return `password_hash`

## Auth (Rick)
- POST /auth/register
- POST /auth/login
- POST /auth/refresh
- GET  /auth/me

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
- What does a HIGH risk transaction do? Proposal: status `PENDING_REVIEW` for staff, not blocked.
- Refresh token storage (stateless vs DB table)
- Roles: CUSTOMER, STAFF, ADMIN
