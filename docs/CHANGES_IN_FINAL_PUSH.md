# Changes made during the final review and push

Everything below was found by reading the merged code and by running probes against it, then fixed and covered by tests.

## Security and correctness (found by probing the merged code)
| Problem found | Fix |
|---|---|
| Any customer could POST a DEPOSIT and mint unlimited money into their own account | Deposits/credits are staff-only (403 for customers) |
| Customer could unfreeze an account that staff had frozen | Customers can only close an empty account; freeze/unfreeze is staff-only |
| A transfer could be sent to another customer's beneficiary | Beneficiary must belong to the sender account's owner |
| Customer chose their own loan interest rate (0%) and could stack pending loans | Bank sets the rate from the duration; one pending application; staff approve/reject endpoint (`PATCH /loans/{id}`) |
| Staff calling `GET /loans` or `/beneficiaries` crashed with a 500 | Staff see all customers' records (optional `customer_id` filter) |
| AI risk was computed but never saved or returned | Stored as `RiskAssessment`, returned as `risk` in the response, readable via `GET /ai/transactions/{id}/risk` |
| Risk model path from settings was ignored | `transaction_service` now loads `RISK_MODEL_PATH` (rule-based fallback if missing) |
| Duplicate `reference` crashed with a 500 on PostgreSQL | Clean 409, nothing changes (checked before and on the database constraint) |
| Account numbers were derived from the last row id (race condition) | Random, uniqueness-checked, with retry |
| Removed beneficiary could not be added again (409) and still showed in lists | List shows ACTIVE by default; re-adding restores it |
| `account_number` accepted any text | 6-20 digits |
| Test database ignored foreign keys, so tests could pass where PostgreSQL fails | Foreign keys enabled in `tests/conftest.py` |
| `postgresql://` URLs picked the wrong driver with current SQLAlchemy (crash on Render) | Always `postgresql+psycopg2://` |

## New
- Beneficiaries, loans (with staff decision and monthly payment), cards, notifications routers
- AI: customer insights, stored risk lookup, model info; risk assessment on transfers as well as transactions
- Notifications for flagged transactions/transfers and loan decisions
- Postman collection (73 requests, 100 assertions), `render.yaml`, Docker start runs migrations
- Docs: architecture diagrams, deployment guide, endpoint contract, README

## Replaced files (so nothing is duplicated)
`app/services/beneficiary_service.py`, `loan_services.py` and `notifications_services.py` were removed: the hardened routers
hold that logic and `notification_service.notify()` adds notifications inside the caller's transaction (they commit together).
`app/schemas/beneficiaries.py` and `loans.py` keep their names with the updated contents.
`tests/test_beneficiaries.py` and `tests/test_loans.py` were replaced with fuller versions.

## Verified
- 199 automated tests pass
- Migration + drift check + full workflow script on a real PostgreSQL server: all checks pass
- Postman collection run with newman, twice in a row against the same database: 100/100 assertions
- Render start command simulated locally (`alembic upgrade head && uvicorn ...`): `/health` and `/docs` respond
