from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.blueprint import DiscoveryBlueprintORM
from app.core.exceptions import BlueprintNotFoundError

class BlueprintService:
    """Service governing blueprint retrieval and matching logic."""

    async def get_active_blueprint(
        self, db: AsyncSession, industry: str, version: Optional[str] = None
    ) -> DiscoveryBlueprintORM:
        """Retrieves the active discovery blueprint for a given industry.
        Falls back to 'Generic' if no matching industry blueprint is found.
        """
        query = select(DiscoveryBlueprintORM).where(
            DiscoveryBlueprintORM.active == True
        )
        
        if version:
            query = query.where(DiscoveryBlueprintORM.version == version)
        else:
            # Order by created_at desc to fetch the newest active version
            query = query.order_by(DiscoveryBlueprintORM.created_at.desc())

        # Try to find industry-specific blueprint
        result = await db.execute(query.where(DiscoveryBlueprintORM.industry == industry))
        blueprint = result.scalars().first()

        if not blueprint:
            # Fallback to Generic blueprint
            result = await db.execute(query.where(DiscoveryBlueprintORM.industry == "Generic"))
            blueprint = result.scalars().first()

        if not blueprint:
            raise BlueprintNotFoundError(industry, version or "latest")

        return blueprint

    async def get_blueprint_stages(self, db: AsyncSession, blueprint_id: any) -> List[str]:
        """Gets list of stages configured in a blueprint."""
        result = await db.execute(
            select(DiscoveryBlueprintORM.stages).where(DiscoveryBlueprintORM.id == blueprint_id)
        )
        stages = result.scalar()
        return stages or []
