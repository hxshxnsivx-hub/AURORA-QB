"""API endpoints for evaluation management"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.evaluation import Evaluation
from models.attempt import Attempt
from schemas.evaluation import (
    EvaluationResponse,
    EvaluationUpdate,
    EvaluationTriggerRequest,
    EvaluationSummaryResponse
)
from agents.task_queue import TaskQueue
from agents.grading_evaluator_agent import GradingEvaluatorAgent
from utils.logger import logger


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation(
    request: EvaluationTriggerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger evaluation for a submitted attempt"""
    
    # Verify attempt exists and belongs to user
    attempt = db.query(Attempt).filter(Attempt.id == request.attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.student_id != current_user.id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Queue evaluation task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="grading_evaluator",
        payload={"attempt_id": str(request.attempt_id)},
        priority=1  # High priority
    )
    
    logger.info("Evaluation queued", extra={
        "task_id": task_id,
        "attempt_id": str(request.attempt_id)
    })
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Evaluation started"
    }


@router.get("/attempt/{attempt_id}", response_model=List[EvaluationResponse])
async def get_attempt_evaluations(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all evaluations for an attempt"""
    
    # Verify attempt exists and user has access
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.student_id != current_user.id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get evaluations
    evaluations = db.query(Evaluation).filter(
        Evaluation.attempt_id == attempt_id
    ).all()
    
    return [EvaluationResponse.from_orm(e) for e in evaluations]


@router.get("/attempt/{attempt_id}/summary", response_model=EvaluationSummaryResponse)
async def get_evaluation_summary(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get evaluation summary for an attempt"""
    
    # Verify attempt exists and user has access
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.student_id != current_user.id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get evaluations
    evaluations = db.query(Evaluation).filter(
        Evaluation.attempt_id == attempt_id
    ).all()
    
    total_score = sum(e.score for e in evaluations)
    max_score = attempt.paper.total_marks
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    # Generate feedback summary
    agent = GradingEvaluatorAgent(db)
    feedback_summary = agent.generate_feedback_summary(attempt_id)
    
    return EvaluationSummaryResponse(
        attempt_id=attempt_id,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        feedback_summary=feedback_summary,
        evaluations=[EvaluationResponse.from_orm(e) for e in evaluations]
    )


@router.patch("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: UUID,
    update_data: EvaluationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Update evaluation (faculty override)"""
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    # Update fields
    if update_data.score is not None:
        # Validate score bounds
        max_score = evaluation.question.marks
        if update_data.score < 0 or update_data.score > max_score:
            raise HTTPException(
                status_code=400,
                detail=f"Score must be between 0 and {max_score}"
            )
        evaluation.score = update_data.score
    
    if update_data.feedback is not None:
        evaluation.feedback = update_data.feedback
    
    if update_data.overridden_by_faculty is not None:
        evaluation.overridden_by_faculty = update_data.overridden_by_faculty
    
    # Recalculate attempt total score
    attempt = evaluation.attempt
    attempt.total_score = sum(
        e.score for e in db.query(Evaluation).filter(
            Evaluation.attempt_id == attempt.id
        ).all()
    )
    
    db.commit()
    db.refresh(evaluation)
    
    logger.info("Evaluation updated", extra={
        "evaluation_id": str(evaluation_id),
        "faculty_id": str(current_user.id)
    })
    
    return EvaluationResponse.from_orm(evaluation)


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(
    evaluation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Delete an evaluation (admin only)"""
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    db.delete(evaluation)
    db.commit()
    
    return None
