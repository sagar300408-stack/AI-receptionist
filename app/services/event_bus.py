import asyncio
import logging
from typing import Callable, Dict, List, Type, Awaitable
from app.domain.events.base import TviraDomainEvent

logger = logging.getLogger("tvira.event_bus")

class DomainEventBus:
    """An asynchronous in-memory Event Bus for domain event distribution."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DomainEventBus, cls).__new__(cls, *args, **kwargs)
            cls._instance._listeners = {}
            cls._instance._global_listeners = []
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[TviraDomainEvent], Awaitable[None]]):
        """Register an async callback for a specific event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} to event: {event_type}")

    def subscribe_all(self, handler: Callable[[TviraDomainEvent], Awaitable[None]]):
        """Register an async callback for all events."""
        self._global_listeners.append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} globally to all events")

    async def publish(self, event: TviraDomainEvent):
        """Dispatches an event to all registered listeners concurrently."""
        logger.info(f"Publishing event '{event.event_type}' for session {event.session_id}")
        
        # Gather handlers
        handlers = list(self._listeners.get(event.event_type, [])) + self._global_listeners
        
        if not handlers:
            return

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            try:
                tasks.append(handler(event))
            except Exception as e:
                logger.error(f"Error initiating handler for event {event.event_type}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# Standard event bus instance
event_bus = DomainEventBus()
