"""API endpoints for paper generation and management"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.paper import Paper, PaperQuestion
from models.question import Question
from schemas.paper import (
    PaperGenerateRequest,
    PaperResponse,
    PaperDetailResponse,
    QuestionInPaper,
    ConstraintValidationResponse
)
from agents.task_queue import TaskQueue
from agents.question_selector_agent import QuestionSelectorAgent
from utils.logger import logger


router = APIRouter(prefix="/papers", tags=["papers"])


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_papers(
    request: PaperGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Generate exam papers based on constraints"""
    
    # Queue paper generation task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="question_selector",
        payload={
            "subject_id": str(request.subject_id),
            "constraints": request.constraints.dict(),
            "num_sets": request.num_sets,
            "faculty_id": str(current_user.id)
        },
        priority=2
    )
    
    logger.info("Paper generation queued", extra={
        "task_id": task_id,
        "subject_id": str(request.subject_id),
        "num_sets": request.num_sets
    })
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": f"Generating {request.num_sets} paper set(s)"
    }


@router.post("/validate-constraints")
async def validate_constraints(
    subject_id: UUID,
    constraints: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ConstraintValidationResponse:
    """Validate paper generation constraints"""
    
    agent = QuestionSelectorAgent(db)
    result = await agent.validate_constraints(subject_id, constraints)
    
    return ConstraintValidationResponse(
        valid=result["valid"],
        errors=result.get("errors", [])
    )


@router.get("/", response_model=List[PaperResponse])
async def list_papers(
    subject_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List papers"""
    query = db.query(Paper)
    
    if current_user.role == UserRole.FACULTY:
        query = query.filter(Paper.faculty_id == current_user.id)
    
    if subject_id:
        query = query.filter(Paper.subject_id == subject_id)
    
    papers = query.order_by(Paper.generation_date.desc()).all()
    
    results = []
    for paper in papers:
        questions_count = db.query(PaperQuestion).filter(
            PaperQuestion.paper_id == paper.id
        ).count()
        
        results.append(PaperResponse(
            id=paper.id,
            subject_id=paper.subject_id,
            faculty_id=paper.faculty_id,
            title=paper.title,
            total_marks=paper.total_marks,
            generation_date=paper.generation_date,
            constraints=paper.constraints,
            questions_count=questions_count
        ))
    
    return results


@router.get("/{paper_id}", response_model=PaperDetailResponse)
async def get_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paper with questions"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check permissions
    if current_user.role == UserRole.FACULTY and paper.faculty_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get questions
    paper_questions = db.query(PaperQuestion, Question).join(
        Question, PaperQuestion.question_id == Question.id
    ).filter(
        PaperQuestion.paper_id == paper_id
    ).order_by(PaperQuestion.order).all()
    
    questions = [
        QuestionInPaper(
            id=q.id,
            text=q.text,
            marks=q.marks,
            type=q.type.value,
            order=pq.order
        )
        for pq, q in paper_questions
    ]
    
    return PaperDetailResponse(
        id=paper.id,
        subject_id=paper.subject_id,
        faculty_id=paper.faculty_id,
        title=paper.title,
        total_marks=paper.total_marks,
        generation_date=paper.generation_date,
        constraints=paper.constraints,
        questions_count=len(questions),
        questions=questions
    )


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Delete a paper"""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    if current_user.role == UserRole.FACULTY and paper.faculty_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(paper)
    db.commit()
    
    return None
