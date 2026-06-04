from fastapi import APIRouter
from app.api.v1.endpoints import sessions
from app.api.v1.endpoints import opportunities
from app.api.v1.endpoints import reports

api_router = APIRouter()
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(opportunities.router, prefix="/sessions", tags=["opportunities"])
api_router.include_router(reports.router, prefix="/sessions", tags=["reports"])
