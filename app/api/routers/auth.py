"""Auth router. Owner: Rick. Implement the endpoints listed in docs/ENDPOINTS.md."""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])
