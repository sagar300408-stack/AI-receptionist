from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.core.database import get_db_session
from app.services.session import SessionService

def get_session_service() -> SessionService:
    """Provides a thread-safe singleton session service instance."""
    return SessionService()
