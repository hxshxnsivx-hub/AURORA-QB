"""API endpoints for roadmap management"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.roadmap import RoadmapTask, RoadmapUpdate
from schemas.roadmap import (
    RoadmapTaskResponse,
    RoadmapTaskUpdate,
    RoadmapUpdateRequest,
    RoadmapUpdateResponse,
    RoadmapTasksReceiveRequest
)
from agents.task_queue import TaskQueue
from agents.roadmap_agent import RoadmapAgent
from utils.logger import logger


router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.post("/update", status_code=status.HTTP_202_ACCEPTED)
async def trigger_roadmap_update(
    request: RoadmapUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Trigger roadmap update for a student"""
    
    # Queue roadmap update task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="roadmap",
        payload={
            "student_id": str(request.student_id),
            "subject_id": str(request.subject_id)
        },
        priority=2
    )
    
    logger.info("Roadmap update queued", extra={
        "task_id": task_id,
        "student_id": str(request.student_id)
    })
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Roadmap update started"
    }


@router.get("/student/{student_id}/tasks", response_model=List[RoadmapTaskResponse])
async def get_student_tasks(
    student_id: UUID,
    completed: bool = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get roadmap tasks for a student"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = db.query(RoadmapTask).filter(RoadmapTask.student_id == student_id)
    
    if completed is not None:
        query = query.filter(RoadmapTask.completed == completed)
    
    tasks = query.order_by(RoadmapTask.due_date.asc()).all()
    
    return [RoadmapTaskResponse.from_orm(t) for t in tasks]


@router.patch("/tasks/{task_id}", response_model=RoadmapTaskResponse)
async def update_task(
    task_id: UUID,
    update_data: RoadmapTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a roadmap task"""
    
    task = db.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permissions
    if current_user.id != task.student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields
    if update_data.completed is not None and update_data.completed != task.completed:
        # Mark as complete
        agent = RoadmapAgent(db)
        await agent.mark_task_complete(task_id, task.student_id)
    
    db.refresh(task)
    
    return RoadmapTaskResponse.from_orm(task)


@router.post("/tasks/receive")
async def receive_tasks(
    request: RoadmapTasksReceiveRequest,
    db: Session = Depends(get_db)
):
    """Receive roadmap tasks from AURORA Learn (webhook)"""
    
    agent = RoadmapAgent(db)
    await agent.receive_roadmap_tasks(request.student_id, request.tasks)
    
    return {
        "status": "received",
        "task_count": len(request.tasks)
    }


@router.get("/student/{student_id}/updates", response_model=List[RoadmapUpdateResponse])
async def get_roadmap_updates(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Get roadmap update history for a student"""
    
    updates = db.query(RoadmapUpdate).filter(
        RoadmapUpdate.student_id == student_id
    ).order_by(RoadmapUpdate.sent_at.desc()).all()
    
    return [RoadmapUpdateResponse.from_orm(u) for u in updates]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Delete a roadmap task (admin only)"""
    
    task = db.query(RoadmapTask).filter(RoadmapTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return None
