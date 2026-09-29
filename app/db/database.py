"""SQLAlchemy engine, session factory and declarative Base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Render provides postgres:// URLs; SQLAlchemy 2.x needs postgresql://
_url = settings.database_url
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
