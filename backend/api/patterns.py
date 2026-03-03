"""
API endpoints for pattern management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.pattern import Pattern
from models.academic import Subject
from agents.pattern_miner_agent import PatternMinerAgent
from agents.task_queue import TaskQueue
from utils.logger import logger


router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/learn", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pattern_learning(
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Trigger pattern learning for a subject.
    
    This queues a task for the Pattern Miner Agent to analyze
    all completed question banks for the subject.
    """
    # Verify subject exists
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found"
        )
    
    # Queue pattern learning task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="pattern_miner",
        payload={"subject_id": str(subject_id)},
        priority=1
    )
    
    logger.info(f"Pattern learning task queued", extra={
        "subject_id": str(subject_id),
        "task_id": task_id,
        "user_id": str(current_user.id)
    })
    
    return {
        "task_id": task_id,
        "subject_id": str(subject_id),
        "status": "queued",
        "message": "Pattern learning task has been queued"
    }


@router.get("/{subject_id}")
async def get_pattern(
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get learned pattern for a subject.
    """
    pattern = db.query(Pattern).filter(Pattern.subject_id == subject_id).first()
    
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pattern found for subject {subject_id}"
        )
    
    return {
        "id": str(pattern.id),
        "subject_id": str(pattern.subject_id),
        "mark_distribution": pattern.mark_distribution,
        "type_distribution": pattern.type_distribution,
        "topic_weights": pattern.topic_weights,
        "difficulty_by_marks": pattern.difficulty_by_marks,
        "confidence": pattern.confidence,
        "created_at": pattern.created_at.isoformat(),
        "updated_at": pattern.updated_at.isoformat()
    }


@router.get("/{subject_id}/visualization")
async def get_pattern_visualization(
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Get pattern visualization data for charts.
    """
    pattern = db.query(Pattern).filter(Pattern.subject_id == subject_id).first()
    
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pattern found for subject {subject_id}"
        )
    
    agent = PatternMinerAgent(db)
    viz_data = agent.get_pattern_visualization_data(pattern)
    
    return viz_data


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pattern(
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """
    Delete pattern for a subject (Admin only).
    """
    pattern = db.query(Pattern).filter(Pattern.subject_id == subject_id).first()
    
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pattern found for subject {subject_id}"
        )
    
    db.delete(pattern)
    db.commit()
    
    logger.info(f"Pattern deleted", extra={
        "subject_id": str(subject_id),
        "admin_id": str(current_user.id)
    })
    
    return None
