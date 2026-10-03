# AI-Powered Banking API

FastAPI backend with JWT auth, role-based access, banking operations and an integrated AI risk-assessment
service. Training project: **synthetic data only**, never real customer financial information.

- Architecture, diagrams and AI flow: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Deploy on Render: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- API contract and how to use auth in a router: [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md)
- Who owns which files: [`docs/OWNERSHIP.md`](docs/OWNERSHIP.md)
- Postman collection: [`postman/AI_Banking_API.postman_collection.json`](postman/AI_Banking_API.postman_collection.json)

## Features
- 10 entities (User, CustomerProfile, Account, Transaction, Beneficiary, Transfer, Card, Loan, RiskAssessment, Notification) with constraints, indexes and Alembic migrations
- Auth: register, login, JWT access + refresh tokens, bcrypt, roles CUSTOMER / STAFF / ADMIN, ownership checks, rate limiting, audit log
- Banking: accounts, transactions, transfers (atomic balance updates), beneficiaries (soft delete), loans (staff approval), cards, notifications
- AI: every transaction and transfer is risk-scored (`risk_score`, `risk_level`, `model_version`) and stored; HIGH risk is `FLAGGED`
  for staff review and the customer is notified. `GET /ai/customers/{id}/insights` returns model-generated insights,
  clearly labelled and separate from banking records. Model failures fall back to a rule-based model and never block a transaction.
- Swagger UI at `/docs`, health check at `/health`

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
alembic upgrade head               # creates the SQLite database and tables
python -m app.db.create_admin admin@example.com 'StrongPass123' 'Admin' 0240000000
uvicorn app.main:app --reload
```
Open http://localhost:8000/docs. Use **Authorize** with the email as username.

## Run the tests
```bash
python -m pytest
```
Tests use an isolated in-memory database with foreign keys enforced. They cover auth, authorization, ownership,
accounts, transactions, transfers, loans, beneficiaries, cards, notifications, AI risk (including model failure),
insights, invalid and unauthorized requests, and database relationships.

## Postman
Import the collection, set `baseUrl`, `adminEmail` and `adminPassword` (the admin created above), then run the
whole collection in the Collection Runner. It registers fresh users on every run and checks 100 assertions.

## Layout
```
app/
  main.py            app, router wiring, CORS, rate limiter, /health
  core/              config, security (bcrypt, JWT), audit, rate limit, logging
  db/                engine, session, Base, create_admin CLI
  models/            SQLAlchemy models
  schemas/           Pydantic request/response models
  api/deps.py        CurrentUser, role guards, ensure_customer_access
  api/routers/       one file per resource
  services/          business logic, ai_risk_service.py, insights_service.py
  ml/                optional trained model (risk_model.pkl)
alembic/             migrations
tests/               pytest suite
postman/             Postman collection
docs/                architecture, deployment, endpoint contract, ownership
```

## AI risk model
`app/services/ai_risk_service.py` loads a trained model bundle from `RISK_MODEL_PATH` if the file exists, otherwise
it uses the rule-based placeholder `rules-0.1`. Swapping in a trained model changes nothing else.
A model bundle is a joblib dict: `{"model": <classifier with predict_proba>, "feature_names": [...], "version": "..."}`.
The features are `amount`, `amount_ratio`, `txn_count_last_hour`, `hour_of_day`, `is_new_beneficiary`.
Any trained model in this project is a demo trained on synthetic data.

## Security notes
Passwords are hashed with bcrypt; `password_hash` and full card numbers are never returned or stored; customers can only
reach their own data (other customers' resources return 404); credits and deposits are posted by staff; customers cannot
change account freezes; production refuses to start with a weak `SECRET_KEY`. Refresh tokens are stateless (no revocation before expiry).
