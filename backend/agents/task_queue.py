"""
Task queue management for agent orchestration.

This module provides task queue operations using Redis as the backend,
including task creation, retrieval, status updates, and dead letter queue handling.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid

from utils.redis_client import redis_client
from utils.logger import logger
from models.agent import AgentTask, AgentTaskStatus


class QueuePriority(str, Enum):
    """Task priority levels"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskQueue:
    """
    Task queue manager using Redis lists and hashes.
    
    Queue structure:
    - tasks:pending:{priority} - List of pending task IDs by priority
    - tasks:processing - Set of currently processing task IDs
    - tasks:completed - List of completed task IDs
    - tasks:failed - List of failed task IDs (dead letter queue)
    - task:{task_id} - Hash containing task data
    """
    
    PENDING_PREFIX = "tasks:pending"
    PROCESSING_SET = "tasks:processing"
    COMPLETED_LIST = "tasks:completed"
    FAILED_LIST = "tasks:failed"
    TASK_PREFIX = "task"
    TASK_EXPIRY = 86400 * 7  # 7 days
    
    def __init__(self):
        self.redis = redis_client
    
    async def create_task(
        self,
        agent_type: str,
        payload: Dict[str, Any],
        priority: QueuePriority = QueuePriority.NORMAL,
        user_id: Optional[int] = None,
        max_retries: int = 3
    ) -> str:
        """
        Create a new task and add to queue.
        
        Args:
            agent_type: Type of agent to process this task
            payload: Task-specific data
            priority: Task priority level
            user_id: User who created the task
            max_retries: Maximum retry attempts
        
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "agent_type": agent_type,
            "payload": json.dumps(payload),
            "priority": priority.value,
            "status": AgentTaskStatus.PENDING.value,
            "user_id": user_id or 0,
            "max_retries": max_retries,
            "retry_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "result": None
        }
        
        # Store task data in hash
        task_key = f"{self.TASK_PREFIX}:{task_id}"
        for key, value in task_data.items():
            if value is not None:
                await self.redis.hset(task_key, key, str(value))
        
        # Set expiry
        await self.redis.client.expire(task_key, self.TASK_EXPIRY)
        
        # Add to pending queue
        queue_key = f"{self.PENDING_PREFIX}:{priority.value}"
        await self.redis.rpush(queue_key, task_id)
        
        logger.info("Task created", extra={
            "task_id": task_id,
            "agent_type": agent_type,
            "priority": priority.value
        })
        
        return task_id
    
    async def get_next_task(
        self,
        agent_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get next task from queue (priority order: high -> normal -> low).
        
        Args:
            agent_type: Filter by agent type (optional)
        
        Returns:
            Task data or None if no tasks available
        """
        # Try each priority level
        for priority in [QueuePriority.HIGH, QueuePriority.NORMAL, QueuePriority.LOW]:
            queue_key = f"{self.PENDING_PREFIX}:{priority.value}"
            
            # Pop task from queue
            task_id = await self.redis.lpop(queue_key)
            
            if task_id:
                # Get task data
                task_data = await self.get_task(task_id)
                
                if not task_data:
                    continue
                
                # Filter by agent type if specified
                if agent_type and task_data.get("agent_type") != agent_type:
                    # Put back in queue
                    await self.redis.rpush(queue_key, task_id)
                    continue
                
                # Mark as processing
                await self.redis.client.sadd(self.PROCESSING_SET, task_id)
                await self.update_task_status(
                    task_id,
                    AgentTaskStatus.PROCESSING,
                    started_at=datetime.utcnow()
                )
                
                logger.info("Task dequeued", extra={
                    "task_id": task_id,
                    "agent_type": task_data.get("agent_type"),
                    "priority": priority.value
                })
                
                return task_data
        
        return None
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data by ID"""
        task_key = f"{self.TASK_PREFIX}:{task_id}"
        task_data = await self.redis.hgetall(task_key)
        
        if not task_data:
            return None
        
        # Parse JSON fields
        if "payload" in task_data:
            task_data["payload"] = json.loads(task_data["payload"])
        if "result" in task_data and task_data["result"]:
            task_data["result"] = json.loads(task_data["result"])
        
        # Convert numeric fields
        if "user_id" in task_data:
            task_data["user_id"] = int(task_data["user_id"])
        if "max_retries" in task_data:
            task_data["max_retries"] = int(task_data["max_retries"])
        if "retry_count" in task_data:
            task_data["retry_count"] = int(task_data["retry_count"])
        
        return task_data
    
    async def update_task_status(
        self,
        task_id: str,
        status: AgentTaskStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """Update task status and metadata"""
        task_key = f"{self.TASK_PREFIX}:{task_id}"
        
        updates = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if error_message:
            updates["error_message"] = error_message
        if result:
            updates["result"] = json.dumps(result)
        if started_at:
            updates["started_at"] = started_at.isoformat()
        if completed_at:
            updates["completed_at"] = completed_at.isoformat()
        
        # Update hash
        for key, value in updates.items():
            await self.redis.hset(task_key, key, str(value))
        
        # Move to appropriate list
        if status == AgentTaskStatus.COMPLETED:
            await self.redis.client.srem(self.PROCESSING_SET, task_id)
            await self.redis.rpush(self.COMPLETED_LIST, task_id)
        elif status == AgentTaskStatus.FAILED:
            await self.redis.client.srem(self.PROCESSING_SET, task_id)
            await self.redis.rpush(self.FAILED_LIST, task_id)
        
        logger.info("Task status updated", extra={
            "task_id": task_id,
            "status": status.value
        })
        
        return True
    
    async def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed task.
        
        Returns:
            True if task can be retried, False otherwise
        """
        task_data = await self.get_task(task_id)
        
        if not task_data:
            return False
        
        retry_count = task_data.get("retry_count", 0)
        max_retries = task_data.get("max_retries", 3)
        
        if retry_count >= max_retries:
            logger.warning("Task max retries exceeded", extra={
                "task_id": task_id,
                "retry_count": retry_count,
                "max_retries": max_retries
            })
            return False
        
        # Increment retry count
        task_key = f"{self.TASK_PREFIX}:{task_id}"
        await self.redis.hset(task_key, "retry_count", str(retry_count + 1))
        await self.redis.hset(task_key, "status", AgentTaskStatus.PENDING.value)
        await self.redis.hset(task_key, "updated_at", datetime.utcnow().isoformat())
        
        # Remove from failed list
        await self.redis.client.lrem(self.FAILED_LIST, 0, task_id)
        
        # Add back to pending queue
        priority = task_data.get("priority", QueuePriority.NORMAL.value)
        queue_key = f"{self.PENDING_PREFIX}:{priority}"
        await self.redis.rpush(queue_key, task_id)
        
        logger.info("Task retried", extra={
            "task_id": task_id,
            "retry_count": retry_count + 1
        })
        
        return True
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        stats = {
            "pending_high": await self.redis.llen(f"{self.PENDING_PREFIX}:high"),
            "pending_normal": await self.redis.llen(f"{self.PENDING_PREFIX}:normal"),
            "pending_low": await self.redis.llen(f"{self.PENDING_PREFIX}:low"),
            "processing": await self.redis.client.scard(self.PROCESSING_SET),
            "completed": await self.redis.llen(self.COMPLETED_LIST),
            "failed": await self.redis.llen(self.FAILED_LIST)
        }
        
        stats["pending_total"] = (
            stats["pending_high"] + 
            stats["pending_normal"] + 
            stats["pending_low"]
        )
        
        return stats
    
    async def get_failed_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get failed tasks from dead letter queue"""
        task_ids = await self.redis.lrange(self.FAILED_LIST, 0, limit - 1)
        
        tasks = []
        for task_id in task_ids:
            task_data = await self.get_task(task_id)
            if task_data:
                tasks.append(task_data)
        
        return tasks
    
    async def clear_completed_tasks(self, older_than_days: int = 7) -> int:
        """Clear completed tasks older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        
        task_ids = await self.redis.lrange(self.COMPLETED_LIST, 0, -1)
        cleared_count = 0
        
        for task_id in task_ids:
            task_data = await self.get_task(task_id)
            
            if not task_data:
                continue
            
            completed_at_str = task_data.get("completed_at")
            if not completed_at_str:
                continue
            
            completed_at = datetime.fromisoformat(completed_at_str)
            
            if completed_at < cutoff_date:
                # Remove from list
                await self.redis.client.lrem(self.COMPLETED_LIST, 0, task_id)
                # Delete task data
                task_key = f"{self.TASK_PREFIX}:{task_id}"
                await self.redis.delete(task_key)
                cleared_count += 1
        
        logger.info("Completed tasks cleared", extra={
            "count": cleared_count,
            "older_than_days": older_than_days
        })
        
        return cleared_count


# Global task queue instance
task_queue = TaskQueue()
