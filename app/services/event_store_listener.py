import logging
from datetime import datetime, timezone
from uuid import uuid4
from app.core.database import SessionLocal
from app.models.event import SessionEventORM
from app.domain.events.base import TviraDomainEvent
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.event_store")

async def db_event_store_listener(event: TviraDomainEvent):
    """Event subscriber callback that writes domain event logs to session_events table."""
    logger.info(f"Database event listener capturing event: {event.event_type} for session: {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            event_orm = SessionEventORM(
                id=uuid4(),
                session_id=event.session_id,
                event_type=event.event_type,
                payload=event.payload,
                timestamp=event.timestamp or datetime.now(timezone.utc)
            )
            db.add(event_orm)
            await db.commit()
            logger.debug(f"Saved event {event.event_type} to database for session {event.session_id}")
        except Exception as e:
            logger.error(f"Failed to save event {event.event_type} to database: {e}")
            await db.rollback()

def register_db_event_listener():
    """Subscribes the database logging listener globally to the domain event bus."""
    event_bus.subscribe_all(db_event_store_listener)
