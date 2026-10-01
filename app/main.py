"""Application entry point. Routers are wired here once; owners only edit their own router files."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routers import accounts, admin, ai, auth, beneficiaries, loans, transactions, transfers
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter

setup_logging()

settings = get_settings()

app = FastAPI(
    title="AI-Powered Banking API",
    version=settings.app_version,
    description="Training-system banking backend with AI risk assessment. Uses synthetic data only.",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, admin, accounts, transactions, transfers, beneficiaries, loans, ai):
    app.include_router(r.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": settings.app_name, "version": settings.app_version}
