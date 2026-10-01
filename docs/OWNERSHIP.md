# File ownership

One owner per file. Do not edit someone else's file without telling them.

| Area | Files | Owner |
|---|---|---|
| Skeleton, config, deployment | `app/main.py`, `app/core/`, `Dockerfile`, `README.md` | Rick |
| Auth, RBAC, ownership checks | `routers/auth.py`, `routers/admin.py`, `app/api/deps.py`, `app/core/security.py`, `app/core/audit.py`, `app/core/rate_limit.py`, `app/db/create_admin.py` | Rick |
| Models, migrations, seed data | `app/models/`, `alembic/`, `app/db/seed.py` | Sakeenah |
| Customer insights | `app/services/insights_service.py`, insights route in `app/api/routers/ai.py` | Sakeenah |
| Accounts, transactions, transfers | `routers/accounts.py`, `transactions.py`, `transfers.py`, matching services and schemas | Banasco |
| AI risk service | `app/services/ai_risk_service.py`, risk persistence, `app/ml/` | Angela |
| Beneficiaries, loans, pagination, notifications | `routers/beneficiaries.py`, `loans.py`, `app/core/pagination.py`, `app/services/notification_service.py` | Reginald |
| Postman collection, slides | `postman/`, `docs/slides/` | Reginald |

Each person writes tests in `tests/test_<their_module>.py`.

Shared files that need a heads-up before changing: `app/main.py`, `app/db/database.py`, `tests/conftest.py`, `requirements.txt`.

## Git rules
- One branch per person: `feature/<name>-<topic>`
- PRs into `main`, Rick reviews before merge
- Small PRs, merged often
- Never commit `.env` or secrets
