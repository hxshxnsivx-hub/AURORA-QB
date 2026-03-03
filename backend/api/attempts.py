"""API endpoints for student exam attempts"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.paper import Paper
from models.attempt import Attempt, StudentAnswer
from schemas.attempt import (
    AttemptStartRequest,
    AttemptResponse,
    AnswerSaveRequest,
    AnswerSubmitRequest,
    AttemptDetailResponse
)
from utils.logger import logger


router = APIRouter(prefix="/attempts", tags=["attempts"])


@router.get("/available-papers", response_model=List[dict])
async def list_available_papers(
    subject_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """List available papers for student"""
    
    query = db.query(Paper)
    
    if subject_id:
        query = query.filter(Paper.subject_id == subject_id)
    
    papers = query.order_by(Paper.generation_date.desc()).all()
    
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "total_marks": p.total_marks,
            "subject_id": str(p.subject_id)
        }
        for p in papers
    ]


@router.post("/start", response_model=AttemptResponse)
async def start_attempt(
    request: AttemptStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """Start a new exam attempt"""
    
    # Check if paper exists
    paper = db.query(Paper).filter(Paper.id == request.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check if student already has an in-progress attempt
    existing = db.query(Attempt).filter(
        Attempt.paper_id == request.paper_id,
        Attempt.student_id == current_user.id,
        Attempt.status == "in_progress"
    ).first()
    
    if existing:
        return AttemptResponse.from_orm(existing)
    
    # Create new attempt
    attempt = Attempt(
        paper_id=request.paper_id,
        student_id=current_user.id,
        start_time=datetime.utcnow(),
        status="in_progress"
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    logger.info("Attempt started", extra={
        "attempt_id": str(attempt.id),
        "student_id": str(current_user.id),
        "paper_id": str(request.paper_id)
    })
    
    return AttemptResponse.from_orm(attempt)


@router.post("/{attempt_id}/save-answer")
async def save_answer(
    attempt_id: UUID,
    request: AnswerSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """Save answer (auto-save)"""
    
    # Verify attempt belongs to student
    attempt = db.query(Attempt).filter(
        Attempt.id == attempt_id,
        Attempt.student_id == current_user.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt is not in progress")
    
    # Save or update answer
    answer = db.query(StudentAnswer).filter(
        StudentAnswer.attempt_id == attempt_id,
        StudentAnswer.question_id == request.question_id
    ).first()
    
    if answer:
        answer.answer_text = request.answer_text
        answer.submitted_at = datetime.utcnow()
    else:
        answer = StudentAnswer(
            attempt_id=attempt_id,
            question_id=request.question_id,
            answer_text=request.answer_text,
            submitted_at=datetime.utcnow()
        )
        db.add(answer)
    
    db.commit()
    
    return {"status": "saved"}


@router.get("/{attempt_id}/resume", response_model=AttemptDetailResponse)
async def resume_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """Resume an in-progress attempt"""
    
    # Verify attempt belongs to student
    attempt = db.query(Attempt).filter(
        Attempt.id == attempt_id,
        Attempt.student_id == current_user.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt is not in progress")
    
    # Get all answers
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.attempt_id == attempt_id
    ).all()
    
    return AttemptDetailResponse(
        id=attempt.id,
        paper_id=attempt.paper_id,
        student_id=attempt.student_id,
        start_time=attempt.start_time,
        submit_time=attempt.submit_time,
        status=attempt.status,
        total_score=attempt.total_score,
        answers=[
            {
                "question_id": str(a.question_id),
                "answer_text": a.answer_text,
                "submitted_at": a.submitted_at
            }
            for a in answers
        ]
    )


@router.post("/{attempt_id}/submit")
async def submit_attempt(
    attempt_id: UUID,
    request: AnswerSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """Submit exam attempt"""
    
    # Verify attempt belongs to student
    attempt = db.query(Attempt).filter(
        Attempt.id == attempt_id,
        Attempt.student_id == current_user.id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already submitted")
    
    # Validate submission
    from models.paper import PaperQuestion
    paper_questions = db.query(PaperQuestion).filter(
        PaperQuestion.paper_id == attempt.paper_id
    ).all()
    
    answered_questions = db.query(StudentAnswer).filter(
        StudentAnswer.attempt_id == attempt_id
    ).all()
    
    answered_ids = {a.question_id for a in answered_questions}
    required_ids = {pq.question_id for pq in paper_questions}
    
    if not required_ids.issubset(answered_ids):
        unanswered = required_ids - answered_ids
        raise HTTPException(
            status_code=400,
            detail=f"Not all questions answered. Missing: {len(unanswered)} questions"
        )
    
    # Mark as submitted
    attempt.status = "submitted"
    attempt.submit_time = datetime.utcnow()
    db.commit()
    
    # Trigger evaluation
    from agents.task_queue import TaskQueue
    task_queue = TaskQueue()
    await task_queue.enqueue_task(
        agent_type="grading_evaluator",
        payload={"attempt_id": str(attempt_id)},
        priority=1
    )
    
    logger.info("Attempt submitted", extra={
        "attempt_id": str(attempt_id),
        "student_id": str(current_user.id)
    })
    
    return {"status": "submitted", "message": "Evaluation in progress"}


@router.get("/student/history", response_model=List[AttemptResponse])
async def get_student_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.STUDENT]))
):
    """Get student's attempt history"""
    
    attempts = db.query(Attempt).filter(
        Attempt.student_id == current_user.id
    ).order_by(Attempt.start_time.desc()).all()
    
    return [AttemptResponse.from_orm(a) for a in attempts]
