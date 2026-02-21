"""
Agent monitoring and management API endpoints.

Provides endpoints for:
- Agent status monitoring
- Queue statistics
- Task management
- Dead letter queue handling
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from database import get_db
from api.dependencies import get_current_user, require_role
from models.user import User, UserRole
from models.agent import AgentTask, AgentTaskStatus, AgentType
from agents.orchestrator import orchestrator
from agents.task_queue import TaskQueue, AgentTaskManager
from agents.retry import RetryManager, RetryConfig
from schemas.agent import (
    AgentTaskResponse,
    AgentStatsResponse,
    QueueStatsResponse,
    RetryTaskRequest
)


router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    Get agent orchestrator statistics
    
    Requires: Faculty or Admin role
    
    Returns:
    - Orchestrator status
    - Worker pool status
    - Registered agents
    - Queue statistics
    """
    stats = await orchestrator.get_stats()
    
    return AgentStatsResponse(**stats)


@router.get("/queues", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    Get queue statistics
    
    Requires: Faculty or Admin role
    
    Returns:
    - Main queue length
    - Processing queue length
    - Dead letter queue length
    """
    stats = await TaskQueue.get_queue_stats()
    
    return QueueStatsResponse(**stats)


@router.get("/tasks", response_model=List[AgentTaskResponse])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    status: Optional[AgentTaskStatus] = Query(None, description="Filter by status"),
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of tasks"),
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    List agent tasks
    
    Requires: Faculty or Admin role
    
    Query Parameters:
    - status: Filter by task status
    - agent_type: Filter by agent type
    - limit: Maximum number of tasks (1-100)
    
    Returns:
    - List of agent tasks
    """
    from sqlalchemy import select
    
    query = select(AgentTask)
    
    if status:
        query = query.where(AgentTask.status == status)
    
    if agent_type:
        query = query.where(AgentTask.agent_type == agent_type)
    
    query = query.order_by(AgentTask.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return [AgentTaskResponse.from_orm(task) for task in tasks]


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    Get agent task by ID
    
    Requires: Faculty or Admin role
    
    Returns:
    - Task details including input/output data
    """
    task = await AgentTaskManager.get_task(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return AgentTaskResponse.from_orm(task)


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: int,
    request: RetryTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Retry a failed task
    
    Requires: Admin role
    
    Request Body:
    - max_attempts: Maximum retry attempts (optional)
    - initial_delay: Initial delay in seconds (optional)
    
    Returns:
    - Success message
    """
    # Get task
    task = await AgentTaskManager.get_task(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != AgentTaskStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not in failed state (current: {task.status.value})"
        )
    
    # Create retry config
    config = RetryConfig(
        max_attempts=request.max_attempts or 3,
        initial_delay=request.initial_delay or 1.0
    )
    
    # Schedule retry
    success = await RetryManager.retry_task(db, task_id, config)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to schedule retry")
    
    return {
        "message": "Task retry scheduled",
        "task_id": task_id,
        "retry_count": task.retry_count + 1
    }


@router.post("/tasks/retry-failed")
async def retry_failed_tasks(
    since_hours: int = Query(24, ge=1, le=168, description="Retry tasks failed in last N hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Retry all failed tasks
    
    Requires: Admin role
    
    Query Parameters:
    - since_hours: Retry tasks failed in last N hours (1-168)
    
    Returns:
    - Number of tasks scheduled for retry
    """
    since = datetime.utcnow() - timedelta(hours=since_hours)
    
    retry_count = await RetryManager.retry_failed_tasks(db, since=since)
    
    return {
        "message": f"Scheduled {retry_count} tasks for retry",
        "retry_count": retry_count,
        "since": since.isoformat()
    }


@router.get("/tasks/pending/count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    Get count of pending tasks
    
    Requires: Faculty or Admin role
    
    Query Parameters:
    - agent_type: Filter by agent type (optional)
    
    Returns:
    - Count of pending tasks
    """
    tasks = await AgentTaskManager.get_pending_tasks(db, agent_type=agent_type)
    
    return {
        "count": len(tasks),
        "agent_type": agent_type.value if agent_type else "all"
    }


@router.get("/tasks/failed/count")
async def get_failed_count(
    db: AsyncSession = Depends(get_db),
    since_hours: int = Query(24, ge=1, le=168, description="Count tasks failed in last N hours"),
    current_user: User = Depends(require_role(UserRole.FACULTY))
):
    """
    Get count of failed tasks
    
    Requires: Faculty or Admin role
    
    Query Parameters:
    - since_hours: Count tasks failed in last N hours (1-168)
    
    Returns:
    - Count of failed tasks
    """
    since = datetime.utcnow() - timedelta(hours=since_hours)
    tasks = await AgentTaskManager.get_failed_tasks(db, since=since)
    
    return {
        "count": len(tasks),
        "since": since.isoformat(),
        "since_hours": since_hours
    }


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Delete an agent task
    
    Requires: Admin role
    
    Returns:
    - Success message
    """
    task = await AgentTaskManager.get_task(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db.delete(task)
    await db.commit()
    
    return {
        "message": "Task deleted",
        "task_id": task_id
    }


@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = Query(30, ge=7, le=365, description="Delete completed tasks older than N days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """
    Clean up old completed tasks
    
    Requires: Admin role
    
    Query Parameters:
    - days: Delete completed tasks older than N days (7-365)
    
    Returns:
    - Number of tasks deleted
    """
    deleted_count = await AgentTaskManager.cleanup_old_tasks(db, days=days)
    
    return {
        "message": f"Deleted {deleted_count} old tasks",
        "deleted_count": deleted_count,
        "days": days
    }
