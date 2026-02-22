"""
API endpoints for agent orchestration and monitoring.

This module provides REST endpoints for:
- Submitting tasks to agents
- Monitoring task status
- Viewing agent statistics
- Managing failed tasks
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional

from schemas.agent import (
    TaskCreate,
    TaskResponse,
    AgentStatusResponse,
    OrchestratorStatsResponse,
    EventPublish,
    EventResponse,
    TaskPriority
)
from agents.orchestrator import orchestrator
from agents.events import event_bus
from agents.task_queue import task_queue
from api.dependencies import get_current_user, require_role
from models.user import User, UserRole
from utils.logger import logger


router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.FACULTY))]
)
async def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new task for agent processing.
    
    **Required Role**: Faculty or Admin
    
    **Parameters**:
    - agent_type: Type of agent to process the task
    - payload: Task-specific data
    - priority: Task priority (high, normal, low)
    
    **Returns**: Created task with ID and status
    """
    try:
        task_id = await orchestrator.submit_task(
            agent_type=task.agent_type,
            payload=task.payload,
            priority=task.priority,
            user_id=current_user.id
        )
        
        # Get task details
        task_data = await task_queue.get_task(task_id)
        
        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created task"
            )
        
        return task_data
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create task", extra={
            "error": str(e),
            "user_id": current_user.id
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task"
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(get_current_user)]
)
async def get_task(task_id: str):
    """
    Get task status and details by ID.
    
    **Required Role**: Any authenticated user
    
    **Parameters**:
    - task_id: Unique task identifier
    
    **Returns**: Task details including status and result
    """
    task_data = await task_queue.get_task(task_id)
    
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return task_data


@router.get(
    "/stats",
    response_model=OrchestratorStatsResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def get_orchestrator_stats():
    """
    Get orchestrator and agent statistics.
    
    **Required Role**: Admin
    
    **Returns**: Complete orchestrator statistics including:
    - Running status
    - Number of agents and workers
    - Queue statistics
    - Per-agent statistics
    """
    try:
        stats = await orchestrator.get_stats()
        return stats
    except Exception as e:
        logger.error("Failed to get orchestrator stats", extra={
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get(
    "/failed-tasks",
    response_model=List[TaskResponse],
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def get_failed_tasks(limit: int = 100):
    """
    Get failed tasks from dead letter queue.
    
    **Required Role**: Admin
    
    **Parameters**:
    - limit: Maximum number of tasks to return (default: 100)
    
    **Returns**: List of failed tasks with error details
    """
    try:
        failed_tasks = await orchestrator.get_failed_tasks(limit=limit)
        return failed_tasks
    except Exception as e:
        logger.error("Failed to get failed tasks", extra={
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve failed tasks"
        )


@router.post(
    "/tasks/{task_id}/retry",
    response_model=TaskResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def retry_task(task_id: str):
    """
    Retry a failed task.
    
    **Required Role**: Admin
    
    **Parameters**:
    - task_id: Task ID to retry
    
    **Returns**: Updated task details
    """
    success = await orchestrator.retry_failed_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task cannot be retried (max retries exceeded or not found)"
        )
    
    # Get updated task data
    task_data = await task_queue.get_task(task_id)
    
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return task_data


@router.delete(
    "/tasks/completed",
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def clear_completed_tasks(older_than_days: int = 7):
    """
    Clear completed tasks older than specified days.
    
    **Required Role**: Admin
    
    **Parameters**:
    - older_than_days: Clear tasks completed more than this many days ago (default: 7)
    
    **Returns**: Number of tasks cleared
    """
    try:
        count = await orchestrator.clear_old_tasks(older_than_days=older_than_days)
        return {
            "message": f"Cleared {count} completed tasks",
            "count": count,
            "older_than_days": older_than_days
        }
    except Exception as e:
        logger.error("Failed to clear completed tasks", extra={
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear completed tasks"
        )


@router.post(
    "/events",
    response_model=EventResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))]
)
async def publish_event(event: EventPublish):
    """
    Publish an event to the event bus.
    
    **Required Role**: Admin
    
    **Parameters**:
    - event_type: Event type/channel name
    - data: Event data
    - metadata: Optional metadata
    
    **Returns**: Event details and number of subscribers notified
    """
    try:
        num_subscribers = await event_bus.publish(
            event_type=event.event_type,
            data=event.data,
            metadata=event.metadata
        )
        
        from datetime import datetime
        
        return {
            "event_type": event.event_type,
            "data": event.data,
            "metadata": event.metadata or {},
            "timestamp": datetime.utcnow(),
            "num_subscribers": num_subscribers
        }
    except Exception as e:
        logger.error("Failed to publish event", extra={
            "error": str(e),
            "event_type": event.event_type
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish event"
        )


@router.get(
    "/health",
    dependencies=[Depends(get_current_user)]
)
async def agent_health_check():
    """
    Check agent system health.
    
    **Required Role**: Any authenticated user
    
    **Returns**: Health status of agent system
    """
    try:
        stats = await orchestrator.get_stats()
        
        # Check if orchestrator is running
        if not stats["running"]:
            return {
                "status": "unhealthy",
                "message": "Orchestrator is not running",
                "details": stats
            }
        
        # Check if there are any agents
        if stats["num_agents"] == 0:
            return {
                "status": "degraded",
                "message": "No agents registered",
                "details": stats
            }
        
        # Check queue health
        queue_stats = stats["queue"]
        if queue_stats["failed"] > 100:
            return {
                "status": "degraded",
                "message": f"High number of failed tasks: {queue_stats['failed']}",
                "details": stats
            }
        
        return {
            "status": "healthy",
            "message": "Agent system is operational",
            "details": stats
        }
        
    except Exception as e:
        logger.error("Health check failed", extra={
            "error": str(e)
        })
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}"
        }
