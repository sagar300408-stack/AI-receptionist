import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.services.event_store_listener import register_db_event_listener
from app.services.opportunity import register_opportunity_listeners
from app.services.report_service import register_report_listeners

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tvira.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def on_startup():
    logger.info("Initializing Tvira Business Discovery Engine...")
    
    # 1. Register domain event bus subscribers
    register_db_event_listener()
    register_opportunity_listeners()
    register_report_listeners()
    
    # 2. Build local database schema asynchronously on startup
    from app.core.database import engine, Base
    # Ensure all models are imported so SQLAlchemy registers them on metadata
    from app.models.session import SessionORM
    from app.models.profile import BusinessProfileORM
    from app.models.response import UserResponseORM
    from app.models.blueprint import DiscoveryBlueprintORM
    from app.models.question import QuestionTemplateORM
    from app.models.event import SessionEventORM
    from app.models.context import BusinessContextORM
    from app.models.opportunity import (
        OpportunityGroupORM, OpportunityTemplateORM, OpportunityRuleORM,
        ScoringProfileORM, OpportunityEvaluationORM, OpportunityResultORM,
        OpportunityEvidenceORM
    )
    from app.models.report import (
        ReportTemplateORM, BusinessReportORM, ReportVersionORM,
        ReportNarrativeEvidenceORM, QualificationResultORM,
        BusinessHealthAssessmentORM, ConsultationRecommendationORM
    )

    async with engine.begin() as conn:
        logger.info("Creating database tables if not existing...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema verification completed.")

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}
