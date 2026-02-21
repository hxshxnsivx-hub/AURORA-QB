"""
Agent Orchestrator for task distribution and coordination.

The orchestrator manages:
- Agent worker pool
- Task distribution to appropriate agents
- Load balancing
- Agent lifecycle management
- Event coordination
"""

import asyncio
from typing import Dict, List, Optional, Type
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import AgentType, AgentTask, AgentTaskStatus
from agents.base import BaseAgent
from agents.task_queue import TaskQueue, AgentTaskManager
from utils.redis_client import redis_client
from utils.logger import logger
from database import get_db


class AgentOrchestrator:
    """
    Orchestrates agent task processing
    
    Manages a pool of agent workers that process tasks from the queue.
    Distributes tasks to appropriate agents based on agent_type.
    """
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize orchestrator
        
        Args:
            max_workers: Maximum number of concurrent workers
        """
        self.max_workers = max_workers
        self.workers: List[asyncio.Task] = []
        self.agents: Dict[AgentType, Type[BaseAgent]] = {}
        self.running = False
        self._shutdown_event = asyncio.Event()
    
    def register_agent(self, agent_type: AgentType, agent_class: Type[BaseAgent]):
        """
        Register an agent type with its implementation
        
        Args:
            agent_type: Type of agent
            agent_class: Agent class (subclass of BaseAgent)
        """
        self.agents[agent_type] = agent_class
        
        logger.info(
            "Agent registered",
            extra={
                "agent_type": agent_type.value,
                "agent_class": agent_class.__name__
            }
        )
    
    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """
        Get agent instance for agent type
        
        Args:
            agent_type: Type of agent
        
        Returns:
            Agent instance or None if not registered
        """
        agent_class = self.agents.get(agent_type)
        
        if agent_class:
            return agent_class(agent_type)
        
        logger.warning(
            "Agent not registered",
            extra={"agent_type": agent_type.value}
        )
        
        return None
    
    async def start(self):
        """Start the orchestrator and worker pool"""
        if self.running:
            logger.warning("Orchestrator already running")
            return
        
        self.running = True
        self._shutdown_event.clear()
        
        # Connect to Redis
        await redis_client.connect()
        
        # Start worker pool
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        
        logger.info(
            "Orchestrator started",
            extra={
                "max_workers": self.max_workers,
                "registered_agents": len(self.agents)
            }
        )
    
    async def stop(self):
        """Stop the orchestrator and worker pool"""
        if not self.running:
            return
        
        logger.info("Stopping orchestrator...")
        
        self.running = False
        self._shutdown_event.set()
        
        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
            self.workers.clear()
        
        # Disconnect from Redis
        await redis_client.disconnect()
        
        logger.info("Orchestrator stopped")
    
    async def _worker(self, worker_id: int):
        """
        Worker coroutine that processes tasks from queue
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(
            "Worker started",
            extra={"worker_id": worker_id}
        )
        
        while self.running:
            try:
                # Get task from queue (5 second timeout)
                task_data = await TaskQueue.dequeue_task(timeout=5)
                
                if not task_data:
                    # No task available, check if shutting down
                    if self._shutdown_event.is_set():
                        break
                    continue
                
                # Process task
                await self._process_task(worker_id, task_data)
                
            except asyncio.CancelledError:
                logger.info(
                    "Worker cancelled",
                    extra={"worker_id": worker_id}
                )
                break
                
            except Exception as e:
                logger.error(
                    "Worker error",
                    extra={
                        "worker_id": worker_id,
                        "error": str(e)
                    }
                )
                # Continue processing
                await asyncio.sleep(1)
        
        logger.info(
            "Worker stopped",
            extra={"worker_id": worker_id}
        )

    
    async def _process_task(self, worker_id: int, task_data: Dict):
        """
        Process a single task
        
        Args:
            worker_id: Worker identifier
            task_data: Task data from queue
        """
        task_id = task_data.get("task_id")
        agent_type_str = task_data.get("agent_type")
        
        logger.info(
            "Worker processing task",
            extra={
                "worker_id": worker_id,
                "task_id": task_id,
                "agent_type": agent_type_str
            }
        )
        
        try:
            # Get agent type
            agent_type = AgentType(agent_type_str)
            
            # Get agent instance
            agent = self.get_agent(agent_type)
            
            if not agent:
                raise ValueError(f"No agent registered for type: {agent_type_str}")
            
            # Get database session
            async for db in get_db():
                try:
                    # Get task from database
                    task = await AgentTaskManager.get_task(db, task_id)
                    
                    if not task:
                        raise ValueError(f"Task not found: {task_id}")
                    
                    # Execute task
                    success = await agent.execute(db, task)
                    
                    if success:
                        # Mark as complete in queue
                        await TaskQueue.complete_task(task_id)
                        
                        # Publish completion event
                        await self._publish_event("task_completed", {
                            "task_id": task_id,
                            "agent_type": agent_type_str,
                            "worker_id": worker_id,
                            "completed_at": datetime.utcnow().isoformat()
                        })
                    else:
                        # Move to dead letter queue
                        await TaskQueue.move_to_dlq(
                            task_id,
                            task.error_message or "Unknown error"
                        )
                        
                        # Publish failure event
                        await self._publish_event("task_failed", {
                            "task_id": task_id,
                            "agent_type": agent_type_str,
                            "worker_id": worker_id,
                            "error": task.error_message,
                            "failed_at": datetime.utcnow().isoformat()
                        })
                    
                finally:
                    await db.close()
                    break
            
        except Exception as e:
            logger.error(
                "Failed to process task",
                extra={
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            
            # Move to dead letter queue
            await TaskQueue.move_to_dlq(task_id, str(e))
    
    async def _publish_event(self, event_type: str, data: Dict):
        """
        Publish event to Redis pub/sub
        
        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            channel = f"agent:events:{event_type}"
            
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await redis_client.publish(channel, event)
            
            logger.debug(
                "Event published",
                extra={
                    "event_type": event_type,
                    "channel": channel
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                extra={
                    "event_type": event_type,
                    "error": str(e)
                }
            )
    
    async def get_stats(self) -> Dict:
        """
        Get orchestrator statistics
        
        Returns:
            Statistics dictionary
        """
        queue_stats = await TaskQueue.get_queue_stats()
        
        return {
            "running": self.running,
            "workers": {
                "total": self.max_workers,
                "active": len([w for w in self.workers if not w.done()])
            },
            "agents": {
                "registered": len(self.agents),
                "types": [at.value for at in self.agents.keys()]
            },
            "queues": queue_stats
        }
    
    async def submit_task(
        self,
        db: AsyncSession,
        agent_type: AgentType,
        input_data: Dict,
        priority: int = 0
    ) -> AgentTask:
        """
        Submit a new task to the orchestrator
        
        Args:
            db: Database session
            agent_type: Type of agent to process task
            input_data: Task input data
            priority: Task priority (higher = more important)
        
        Returns:
            Created AgentTask
        """
        # Create task in database and enqueue
        task = await AgentTaskManager.create_task(
            db,
            agent_type,
            input_data,
            priority
        )
        
        # Publish task created event
        await self._publish_event("task_created", {
            "task_id": task.id,
            "agent_type": agent_type.value,
            "priority": priority,
            "created_at": task.created_at.isoformat()
        })
        
        logger.info(
            "Task submitted to orchestrator",
            extra={
                "task_id": task.id,
                "agent_type": agent_type.value,
                "priority": priority
            }
        )
        
        return task


# Global orchestrator instance
orchestrator = AgentOrchestrator(max_workers=5)
