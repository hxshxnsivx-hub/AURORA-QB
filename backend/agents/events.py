"""
Event system for agent coordination.

Provides pub/sub event handling for:
- Task lifecycle events
- Agent status events
- System events
- Custom events
"""

import asyncio
from typing import Dict, Callable, List, Any, Optional
from datetime import datetime
from enum import Enum

from utils.redis_client import redis_client
from utils.logger import logger


class EventType(str, Enum):
    """Standard event types"""
    
    # Task events
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRIED = "task_retried"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_ERROR = "agent_error"
    
    # System events
    ORCHESTRATOR_STARTED = "orchestrator_started"
    ORCHESTRATOR_STOPPED = "orchestrator_stopped"
    QUEUE_FULL = "queue_full"
    QUEUE_EMPTY = "queue_empty"
    
    # Custom events
    CUSTOM = "custom"


class EventBus:
    """
    Event bus for pub/sub messaging
    
    Allows components to publish and subscribe to events
    without direct coupling.
    """
    
    def __init__(self):
        """Initialize event bus"""
        self.handlers: Dict[str, List[Callable]] = {}
        self.running = False
        self._listener_task: Optional[asyncio.Task] = None
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """
        Subscribe to event type
        
        Args:
            event_type: Type of event to subscribe to
            handler: Async function to call when event occurs
        """
        channel = f"agent:events:{event_type.value}"
        
        if channel not in self.handlers:
            self.handlers[channel] = []
        
        self.handlers[channel].append(handler)
        
        logger.info(
            "Event handler subscribed",
            extra={
                "event_type": event_type.value,
                "handler": handler.__name__,
                "total_handlers": len(self.handlers[channel])
            }
        )
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """
        Unsubscribe from event type
        
        Args:
            event_type: Type of event
            handler: Handler function to remove
        """
        channel = f"agent:events:{event_type.value}"
        
        if channel in self.handlers and handler in self.handlers[channel]:
            self.handlers[channel].remove(handler)
            
            logger.info(
                "Event handler unsubscribed",
                extra={
                    "event_type": event_type.value,
                    "handler": handler.__name__
                }
            )
    
    async def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Publish event
        
        Args:
            event_type: Type of event
            data: Event data
            metadata: Optional metadata
        """
        channel = f"agent:events:{event_type.value}"
        
        event = {
            "type": event_type.value,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            await redis_client.publish(channel, event)
            
            logger.debug(
                "Event published",
                extra={
                    "event_type": event_type.value,
                    "data_keys": list(data.keys())
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                extra={
                    "event_type": event_type.value,
                    "error": str(e)
                }
            )
    
    async def start(self):
        """Start event listener"""
        if self.running:
            logger.warning("Event bus already running")
            return
        
        self.running = True
        
        # Connect to Redis
        await redis_client.connect()
        
        # Subscribe to all channels with handlers
        if self.handlers:
            await redis_client.subscribe(*self.handlers.keys())
        
        # Start listener task
        self._listener_task = asyncio.create_task(self._listen())
        
        logger.info(
            "Event bus started",
            extra={
                "channels": len(self.handlers),
                "total_handlers": sum(len(h) for h in self.handlers.values())
            }
        )
    
    async def stop(self):
        """Stop event listener"""
        if not self.running:
            return
        
        logger.info("Stopping event bus...")
        
        self.running = False
        
        # Unsubscribe from all channels
        if self.handlers:
            await redis_client.unsubscribe(*self.handlers.keys())
        
        # Cancel listener task
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event bus stopped")
    
    async def _listen(self):
        """Listen for events and dispatch to handlers"""
        logger.info("Event listener started")
        
        while self.running:
            try:
                # Get message from subscribed channels
                message = await redis_client.get_message(timeout=1.0)
                
                if message:
                    await self._dispatch(message)
                
            except asyncio.CancelledError:
                break
                
            except Exception as e:
                logger.error(
                    "Event listener error",
                    extra={"error": str(e)}
                )
                await asyncio.sleep(1)
        
        logger.info("Event listener stopped")
    
    async def _dispatch(self, message: Dict):
        """
        Dispatch event to handlers
        
        Args:
            message: Message from Redis
        """
        channel = message.get("channel")
        data = message.get("data", {})
        
        handlers = self.handlers.get(channel, [])
        
        if not handlers:
            return
        
        event_type = data.get("type")
        event_data = data.get("data", {})
        
        logger.debug(
            "Dispatching event",
            extra={
                "event_type": event_type,
                "handlers": len(handlers)
            }
        )
        
        # Call all handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
                    
            except Exception as e:
                logger.error(
                    "Event handler error",
                    extra={
                        "event_type": event_type,
                        "handler": handler.__name__,
                        "error": str(e)
                    }
                )


# Global event bus instance
event_bus = EventBus()


# Convenience functions

async def publish_task_created(task_id: int, agent_type: str, priority: int = 0):
    """Publish task created event"""
    await event_bus.publish(
        EventType.TASK_CREATED,
        {
            "task_id": task_id,
            "agent_type": agent_type,
            "priority": priority
        }
    )


async def publish_task_completed(task_id: int, agent_type: str, duration_seconds: float):
    """Publish task completed event"""
    await event_bus.publish(
        EventType.TASK_COMPLETED,
        {
            "task_id": task_id,
            "agent_type": agent_type,
            "duration_seconds": duration_seconds
        }
    )


async def publish_task_failed(task_id: int, agent_type: str, error: str):
    """Publish task failed event"""
    await event_bus.publish(
        EventType.TASK_FAILED,
        {
            "task_id": task_id,
            "agent_type": agent_type,
            "error": error
        }
    )


async def publish_agent_error(agent_type: str, error: str, task_id: Optional[int] = None):
    """Publish agent error event"""
    await event_bus.publish(
        EventType.AGENT_ERROR,
        {
            "agent_type": agent_type,
            "error": error,
            "task_id": task_id
        }
    )
