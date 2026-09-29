"""Application entry point. Routers are wired here once; owners only edit their own router files."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import accounts, ai, auth, beneficiaries, loans, transactions, transfers
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI-Powered Banking API",
    version=settings.app_version,
    description="Training-system banking backend with AI risk assessment. Uses synthetic data only.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, accounts, transactions, transfers, beneficiaries, loans, ai):
    app.include_router(r.router)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "service": settings.app_name, "version": settings.app_version}
