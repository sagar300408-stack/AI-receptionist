from fastapi import APIRouter
from app.api.v1.endpoints import sessions
from app.api.v1.endpoints import opportunities
from app.api.v1.endpoints import reports
from app.api.v1.endpoints import constraints
from app.api.v1.endpoints import applicability
from app.api.v1.endpoints import solutions
from app.api.v1.endpoints import reviews

api_router = APIRouter()
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(opportunities.router, prefix="/sessions", tags=["opportunities"])
api_router.include_router(reports.router, prefix="/sessions", tags=["reports"])
api_router.include_router(constraints.router, prefix="/sessions", tags=["constraints"])
api_router.include_router(applicability.router, prefix="/sessions", tags=["applicability"])
api_router.include_router(solutions.router, prefix="/sessions", tags=["solutions"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])




