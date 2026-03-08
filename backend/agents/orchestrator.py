"""
Agent Orchestrator for managing and coordinating multiple agents.

The orchestrator is responsible for:
- Agent lifecycle management
- Task distribution to appropriate agents
- Monitoring agent health and performance
- Handling agent failures and retries
"""

from typing import Dict, List, Optional, Type
import asyncio
from datetime import datetime

from agents.base import Agent, AgentStatus
from agents.task_queue import task_queue, QueuePriority
from agents.events import event_bus
from utils.logger import logger


class AgentOrchestrator:
    """
    Orchestrator for managing multiple agents and task distribution.
    
    The orchestrator maintains a registry of agents and coordinates
    task processing across the agent pool.
    """
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.num_workers = 3  # Number of concurrent workers per agent type
    
    def register_agent(self, agent: Agent):
        """
        Register an agent with the orchestrator.
        
        Args:
            agent: Agent instance to register
        """
        self.agents[agent.agent_type] = agent
        logger.info("Agent registered", extra={
            "agent_type": agent.agent_type,
            "total_agents": len(self.agents)
        })
    
    def unregister_agent(self, agent_type: str):
        """
        Unregister an agent.
        
        Args:
            agent_type: Type of agent to unregister
        """
        if agent_type in self.agents:
            del self.agents[agent_type]
            logger.info("Agent unregistered", extra={
                "agent_type": agent_type,
                "total_agents": len(self.agents)
            })
    
    def get_agent(self, agent_type: str) -> Optional[Agent]:
        """Get agent by type"""
        return self.agents.get(agent_type)
    
    async def start(self):
        """Start the orchestrator and all registered agents"""
        if self.running:
            logger.warning("Orchestrator already running")
            return
        
        self.running = True
        
        # Start all agents
        for agent in self.agents.values():
            await agent.start()
        
        # Start worker tasks for each agent type
        for agent_type in self.agents.keys():
            for i in range(self.num_workers):
                worker_task = asyncio.create_task(
                    self._worker(agent_type, worker_id=i)
                )
                self.worker_tasks.append(worker_task)
        
        logger.info("Orchestrator started", extra={
            "num_agents": len(self.agents),
            "num_workers": len(self.worker_tasks)
        })
    
    async def stop(self):
        """Stop the orchestrator and all workers"""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        
        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()
        
        logger.info("Orchestrator stopped")
    
    async def _worker(self, agent_type: str, worker_id: int):
        """
        Worker coroutine that processes tasks for a specific agent type.
        
        Args:
            agent_type: Type of agent this worker serves
            worker_id: Unique worker identifier
        """
        agent = self.get_agent(agent_type)
        
        if not agent:
            logger.error("Worker started for unknown agent type", extra={
                "agent_type": agent_type,
                "worker_id": worker_id
            })
            return
        
        logger.info("Worker started", extra={
            "agent_type": agent_type,
            "worker_id": worker_id
        })
        
        while self.running:
            try:
                # Get next task from queue
                task_data = await task_queue.get_next_task(agent_type=agent_type)
                
                if not task_data:
                    # No tasks available, wait before checking again
                    await asyncio.sleep(1)
                    continue
                
                task_id = task_data.get("task_id")
                
                logger.info("Worker processing task", extra={
                    "agent_type": agent_type,
                    "worker_id": worker_id,
                    "task_id": task_id
                })
                
                # Execute task
                result = await agent.execute_task(task_data)
                
                # Update task status based on result
                if result.get("success"):
                    from models.agent import AgentTaskStatus
                    await task_queue.update_task_status(
                        task_id,
                        AgentTaskStatus.COMPLETED,
                        result=result.get("result"),
                        completed_at=datetime.utcnow()
                    )
                    
                    # Publish task completed event
                    await event_bus.publish(
                        f"task.{agent_type}.completed",
                        {
                            "task_id": task_id,
                            "agent_type": agent_type,
                            "result": result.get("result")
                        }
                    )
                else:
                    # Task failed, check if should retry
                    should_retry = await task_queue.retry_task(task_id)
                    
                    if not should_retry:
                        # Max retries exceeded, mark as failed
                        from models.agent import AgentTaskStatus
                        await task_queue.update_task_status(
                            task_id,
                            AgentTaskStatus.FAILED,
                            error_message=result.get("error"),
                            completed_at=datetime.utcnow()
                        )
                        
                        # Publish task failed event
                        await event_bus.publish(
                            f"task.{agent_type}.failed",
                            {
                                "task_id": task_id,
                                "agent_type": agent_type,
                                "error": result.get("error")
                            }
                        )
                
            except asyncio.CancelledError:
                logger.info("Worker cancelled", extra={
                    "agent_type": agent_type,
                    "worker_id": worker_id
                })
                break
            except Exception as e:
                logger.error("Worker error", extra={
                    "agent_type": agent_type,
                    "worker_id": worker_id,
                    "error": str(e)
                })
                await asyncio.sleep(5)  # Wait before retrying
    
    async def submit_task(
        self,
        agent_type: str,
        payload: Dict,
        priority: QueuePriority = QueuePriority.NORMAL,
        user_id: Optional[int] = None
    ) -> str:
        """
        Submit a task to be processed by an agent.
        
        Args:
            agent_type: Type of agent to process the task
            payload: Task-specific data
            priority: Task priority level
            user_id: User who submitted the task
        
        Returns:
            Task ID
        
        Raises:
            ValueError: If agent type is not registered
        """
        if agent_type not in self.agents:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        task_id = await task_queue.create_task(
            agent_type=agent_type,
            payload=payload,
            priority=priority,
            user_id=user_id
        )
        
        # Publish task created event
        await event_bus.publish(
            f"task.{agent_type}.created",
            {
                "task_id": task_id,
                "agent_type": agent_type,
                "priority": priority.value
            }
        )
        
        logger.info("Task submitted", extra={
            "task_id": task_id,
            "agent_type": agent_type,
            "priority": priority.value
        })
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task"""
        return await task_queue.get_task(task_id)
    
    async def get_stats(self) -> Dict:
        """Get orchestrator statistics"""
        queue_stats = await task_queue.get_queue_stats()
        
        agent_stats = {}
        for agent_type, agent in self.agents.items():
            agent_stats[agent_type] = agent.get_status()
        
        return {
            "running": self.running,
            "num_agents": len(self.agents),
            "num_workers": len(self.worker_tasks),
            "queue": queue_stats,
            "agents": agent_stats
        }
    
    async def get_failed_tasks(self, limit: int = 100) -> List[Dict]:
        """Get failed tasks from dead letter queue"""
        return await task_queue.get_failed_tasks(limit=limit)
    
    async def retry_failed_task(self, task_id: str) -> bool:
        """Retry a failed task"""
        return await task_queue.retry_task(task_id)
    
    async def clear_old_tasks(self, older_than_days: int = 7) -> int:
        """Clear completed tasks older than specified days"""
        return await task_queue.clear_completed_tasks(older_than_days=older_than_days)


# Global orchestrator instance
orchestrator = AgentOrchestrator()
