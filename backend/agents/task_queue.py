"""
Agent task queue management.

Manages AgentTask lifecycle:
- Task creation and queuing
- Task status tracking
- Task retrieval and completion
- Dead letter queue for failed tasks
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from models.agent import AgentTask, AgentTaskStatus, AgentType
from utils.redis_client import redis_client
from utils.logger import logger


class TaskQueue:
    """Redis-based task queue for agent orchestration"""
    
    # Queue names
    MAIN_QUEUE = "agent:tasks:main"
    PROCESSING_QUEUE = "agent:tasks:processing"
    DEAD_LETTER_QUEUE = "agent:tasks:dlq"
    
    # Task timeout (30 minutes)
    TASK_TIMEOUT = 1800
    
    @staticmethod
    async def enqueue_task(task_id: int, agent_type: str, priority: int = 0) -> bool:
        """
        Add task to queue
        
        Args:
            task_id: AgentTask ID
            agent_type: Type of agent to process task
            priority: Task priority (higher = more important)
        
        Returns:
            True if enqueued successfully
        """
        try:
            task_data = {
                "task_id": task_id,
                "agent_type": agent_type,
                "priority": priority,
                "enqueued_at": datetime.utcnow().isoformat()
            }
            
            await redis_client.enqueue(TaskQueue.MAIN_QUEUE, task_data)
            
            logger.info(
                "Task enqueued",
                extra={
                    "task_id": task_id,
                    "agent_type": agent_type,
                    "priority": priority
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to enqueue task",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            return False

    
    @staticmethod
    async def dequeue_task(timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get next task from queue (blocking)
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Task data or None
        """
        try:
            task_data = await redis_client.dequeue(TaskQueue.MAIN_QUEUE, timeout)
            
            if task_data:
                # Move to processing queue
                await redis_client.enqueue(TaskQueue.PROCESSING_QUEUE, task_data)
                
                logger.info(
                    "Task dequeued",
                    extra={
                        "task_id": task_data.get("task_id"),
                        "agent_type": task_data.get("agent_type")
                    }
                )
            
            return task_data
            
        except Exception as e:
            logger.error("Failed to dequeue task", extra={"error": str(e)})
            return None
    
    @staticmethod
    async def complete_task(task_id: int) -> bool:
        """
        Mark task as complete and remove from processing queue
        
        Args:
            task_id: AgentTask ID
        
        Returns:
            True if successful
        """
        try:
            # Find and remove from processing queue
            processing_tasks = await redis_client.peek_queue(TaskQueue.PROCESSING_QUEUE)
            
            for i, task_data in enumerate(processing_tasks):
                if task_data.get("task_id") == task_id:
                    # Remove from processing queue
                    # Note: This is a simplified approach
                    # In production, use a hash map for O(1) removal
                    await redis_client.delete(f"task:processing:{task_id}")
                    
                    logger.info(
                        "Task completed",
                        extra={"task_id": task_id}
                    )
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Failed to complete task",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            return False
    
    @staticmethod
    async def move_to_dlq(task_id: int, error: str) -> bool:
        """
        Move failed task to dead letter queue
        
        Args:
            task_id: AgentTask ID
            error: Error message
        
        Returns:
            True if successful
        """
        try:
            task_data = {
                "task_id": task_id,
                "error": error,
                "failed_at": datetime.utcnow().isoformat()
            }
            
            await redis_client.enqueue(TaskQueue.DEAD_LETTER_QUEUE, task_data)
            
            logger.warning(
                "Task moved to DLQ",
                extra={
                    "task_id": task_id,
                    "error": error
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to move task to DLQ",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            return False
    
    @staticmethod
    async def get_queue_stats() -> Dict[str, int]:
        """Get statistics for all queues"""
        try:
            return {
                "main_queue": await redis_client.queue_length(TaskQueue.MAIN_QUEUE),
                "processing_queue": await redis_client.queue_length(TaskQueue.PROCESSING_QUEUE),
                "dead_letter_queue": await redis_client.queue_length(TaskQueue.DEAD_LETTER_QUEUE)
            }
        except Exception as e:
            logger.error("Failed to get queue stats", extra={"error": str(e)})
            return {"main_queue": 0, "processing_queue": 0, "dead_letter_queue": 0}


class AgentTaskManager:
    """Database-backed agent task management"""
    
    @staticmethod
    async def create_task(
        db: AsyncSession,
        agent_type: AgentType,
        input_data: dict,
        priority: int = 0
    ) -> AgentTask:
        """
        Create new agent task
        
        Args:
            db: Database session
            agent_type: Type of agent
            input_data: Task input data
            priority: Task priority
        
        Returns:
            Created AgentTask
        """
        task = AgentTask(
            agent_type=agent_type,
            status=AgentTaskStatus.PENDING,
            input_data=input_data,
            priority=priority
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # Enqueue task
        await TaskQueue.enqueue_task(task.id, agent_type.value, priority)
        
        logger.info(
            "Agent task created",
            extra={
                "task_id": task.id,
                "agent_type": agent_type.value,
                "priority": priority
            }
        )
        
        return task

    
    @staticmethod
    async def get_task(db: AsyncSession, task_id: int) -> Optional[AgentTask]:
        """Get task by ID"""
        result = await db.execute(
            select(AgentTask).where(AgentTask.id == task_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_task_status(
        db: AsyncSession,
        task_id: int,
        status: AgentTaskStatus,
        output_data: Optional[dict] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update task status
        
        Args:
            db: Database session
            task_id: Task ID
            status: New status
            output_data: Task output data
            error_message: Error message if failed
        
        Returns:
            True if successful
        """
        try:
            update_data = {"status": status}
            
            if status == AgentTaskStatus.IN_PROGRESS:
                update_data["started_at"] = datetime.utcnow()
            elif status in [AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED]:
                update_data["completed_at"] = datetime.utcnow()
            
            if output_data:
                update_data["output_data"] = output_data
            
            if error_message:
                update_data["error_message"] = error_message
            
            await db.execute(
                update(AgentTask)
                .where(AgentTask.id == task_id)
                .values(**update_data)
            )
            await db.commit()
            
            logger.info(
                "Task status updated",
                extra={
                    "task_id": task_id,
                    "status": status.value
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update task status",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            await db.rollback()
            return False
    
    @staticmethod
    async def get_pending_tasks(
        db: AsyncSession,
        agent_type: Optional[AgentType] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get pending tasks"""
        query = select(AgentTask).where(
            AgentTask.status == AgentTaskStatus.PENDING
        )
        
        if agent_type:
            query = query.where(AgentTask.agent_type == agent_type)
        
        query = query.order_by(
            AgentTask.priority.desc(),
            AgentTask.created_at.asc()
        ).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_failed_tasks(
        db: AsyncSession,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get failed tasks"""
        query = select(AgentTask).where(
            AgentTask.status == AgentTaskStatus.FAILED
        )
        
        if since:
            query = query.where(AgentTask.created_at >= since)
        
        query = query.order_by(AgentTask.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def retry_task(db: AsyncSession, task_id: int) -> bool:
        """
        Retry a failed task
        
        Args:
            db: Database session
            task_id: Task ID
        
        Returns:
            True if successful
        """
        try:
            task = await AgentTaskManager.get_task(db, task_id)
            
            if not task or task.status != AgentTaskStatus.FAILED:
                return False
            
            # Increment retry count
            task.retry_count += 1
            task.status = AgentTaskStatus.PENDING
            task.error_message = None
            
            await db.commit()
            
            # Re-enqueue
            await TaskQueue.enqueue_task(task.id, task.agent_type.value, task.priority)
            
            logger.info(
                "Task retry initiated",
                extra={
                    "task_id": task_id,
                    "retry_count": task.retry_count
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to retry task",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            await db.rollback()
            return False
    
    @staticmethod
    async def cleanup_old_tasks(
        db: AsyncSession,
        days: int = 30
    ) -> int:
        """
        Clean up completed tasks older than specified days
        
        Args:
            db: Database session
            days: Number of days to keep
        
        Returns:
            Number of tasks deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            result = await db.execute(
                select(AgentTask).where(
                    AgentTask.status == AgentTaskStatus.COMPLETED,
                    AgentTask.completed_at < cutoff_date
                )
            )
            tasks = result.scalars().all()
            
            for task in tasks:
                await db.delete(task)
            
            await db.commit()
            
            logger.info(
                "Old tasks cleaned up",
                extra={
                    "count": len(tasks),
                    "cutoff_date": cutoff_date.isoformat()
                }
            )
            
            return len(tasks)
            
        except Exception as e:
            logger.error(
                "Failed to cleanup old tasks",
                extra={"error": str(e)}
            )
            await db.rollback()
            return 0
