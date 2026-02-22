"""
Event publishing and subscription system for agent communication.

This module provides a pub/sub event bus using Redis for inter-agent
communication and system-wide event notifications.
"""

from typing import Dict, Any, Callable, List
import asyncio
import json
from datetime import datetime

from utils.redis_client import redis_client
from utils.logger import logger


class EventBus:
    """
    Event bus for publishing and subscribing to system events.
    
    Events are published to Redis channels and can be subscribed to
    by multiple consumers for real-time notifications.
    """
    
    def __init__(self):
        self.redis = redis_client
        self.subscribers: Dict[str, List[Callable]] = {}
        self.pubsub = None
        self.listener_task: asyncio.Task = None
    
    async def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> int:
        """
        Publish an event to a channel.
        
        Args:
            event_type: Event type/channel name
            data: Event data
            metadata: Optional metadata
        
        Returns:
            Number of subscribers that received the message
        """
        event = {
            "event_type": event_type,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        event_json = json.dumps(event)
        
        # Publish to Redis channel
        num_subscribers = await self.redis.publish(event_type, event_json)
        
        logger.info("Event published", extra={
            "event_type": event_type,
            "num_subscribers": num_subscribers
        })
        
        # Also call local subscribers
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error("Event callback error", extra={
                        "event_type": event_type,
                        "error": str(e)
                    })
        
        return num_subscribers
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to an event type with a callback function.
        
        Args:
            event_type: Event type to subscribe to
            callback: Function to call when event is received
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append(callback)
        
        logger.info("Event subscription added", extra={
            "event_type": event_type,
            "num_subscribers": len(self.subscribers[event_type])
        })
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """
        Unsubscribe a callback from an event type.
        
        Args:
            event_type: Event type to unsubscribe from
            callback: Callback function to remove
        """
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
                logger.info("Event subscription removed", extra={
                    "event_type": event_type
                })
            except ValueError:
                pass
    
    async def start_listener(self, *channels: str):
        """
        Start listening to Redis pub/sub channels.
        
        Args:
            channels: Channel names to listen to
        """
        if self.listener_task and not self.listener_task.done():
            logger.warning("Event listener already running")
            return
        
        self.pubsub = await self.redis.subscribe(*channels)
        
        if not self.pubsub:
            logger.error("Failed to create pub/sub connection")
            return
        
        self.listener_task = asyncio.create_task(self._listen())
        
        logger.info("Event listener started", extra={
            "channels": channels
        })
    
    async def stop_listener(self):
        """Stop the event listener"""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        logger.info("Event listener stopped")
    
    async def _listen(self):
        """Internal listener coroutine"""
        try:
            while True:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message and message["type"] == "message":
                    try:
                        event = json.loads(message["data"])
                        event_type = event.get("event_type")
                        
                        # Call local subscribers
                        if event_type in self.subscribers:
                            for callback in self.subscribers[event_type]:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(event)
                                    else:
                                        callback(event)
                                except Exception as e:
                                    logger.error("Event callback error", extra={
                                        "event_type": event_type,
                                        "error": str(e)
                                    })
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse event", extra={
                            "error": str(e)
                        })
                
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
        except Exception as e:
            logger.error("Event listener error", extra={
                "error": str(e)
            })


# Global event bus instance
event_bus = EventBus()


# Common event types
class EventType:
    """Common event type constants"""
    
    # Task events
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRIED = "task.retried"
    
    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"
    
    # Ingestion events
    FILE_UPLOADED = "file.uploaded"
    QUESTIONS_EXTRACTED = "questions.extracted"
    TAGS_SUGGESTED = "tags.suggested"
    
    # Pattern mining events
    PATTERN_LEARNED = "pattern.learned"
    PATTERN_UPDATED = "pattern.updated"
    
    # Paper generation events
    PAPER_GENERATION_STARTED = "paper.generation.started"
    PAPER_GENERATED = "paper.generated"
    PAPER_GENERATION_FAILED = "paper.generation.failed"
    
    # Evaluation events
    ATTEMPT_SUBMITTED = "attempt.submitted"
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"
    
    # Performance analysis events
    WEAKNESS_IDENTIFIED = "weakness.identified"
    ROADMAP_UPDATED = "roadmap.updated"
