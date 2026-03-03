"""API endpoints for answer key generation and management"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.answer_key import AnswerKey
from models.paper import Paper, PaperQuestion
from models.question import Question
from schemas.answer_key import (
    AnswerKeyResponse,
    AnswerKeyUpdate,
    AnswerKeyGenerationRequest,
    AnswerKeyGenerationResponse,
    AnswerKeyBulkResponse
)
from agents.task_queue import TaskQueue
from agents.answer_key_generator_agent import AnswerKeyGeneratorAgent
from utils.logger import logger


router = APIRouter(prefix="/answer-keys", tags=["answer-keys"])


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_answer_keys(
    request: AnswerKeyGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
) -> AnswerKeyGenerationResponse:
    """Generate answer keys for all questions in a paper"""
    
    # Verify paper exists
    paper = db.query(Paper).filter(Paper.id == request.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check permissions
    if current_user.role == UserRole.FACULTY and paper.faculty_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Queue answer key generation task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="answer_key_generator",
        payload={"paper_id": str(request.paper_id)},
        priority=2
    )
    
    logger.info("Answer key generation queued", extra={
        "task_id": task_id,
        "paper_id": str(request.paper_id)
    })
    
    return AnswerKeyGenerationResponse(
        task_id=task_id,
        status="queued",
        message="Answer key generation started"
    )


@router.get("/paper/{paper_id}", response_model=AnswerKeyBulkResponse)
async def get_paper_answer_keys(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all answer keys for a paper"""
    
    # Verify paper exists
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check permissions
    if current_user.role == UserRole.FACULTY and paper.faculty_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get all questions in paper
    paper_questions = db.query(PaperQuestion).filter(
        PaperQuestion.paper_id == paper_id
    ).all()
    
    question_ids = [pq.question_id for pq in paper_questions]
    
    # Get answer keys
    answer_keys = db.query(AnswerKey).filter(
        AnswerKey.question_id.in_(question_ids)
    ).all()
    
    return AnswerKeyBulkResponse(
        paper_id=paper_id,
        generated_count=len(answer_keys),
        total_questions=len(paper_questions),
        answer_keys=[AnswerKeyResponse.from_orm(ak) for ak in answer_keys]
    )


@router.get("/{answer_key_id}", response_model=AnswerKeyResponse)
async def get_answer_key(
    answer_key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific answer key"""
    
    answer_key = db.query(AnswerKey).filter(AnswerKey.id == answer_key_id).first()
    
    if not answer_key:
        raise HTTPException(status_code=404, detail="Answer key not found")
    
    return AnswerKeyResponse.from_orm(answer_key)


@router.patch("/{answer_key_id}", response_model=AnswerKeyResponse)
async def update_answer_key(
    answer_key_id: UUID,
    update_data: AnswerKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Update an answer key (faculty review)"""
    
    answer_key = db.query(AnswerKey).filter(AnswerKey.id == answer_key_id).first()
    
    if not answer_key:
        raise HTTPException(status_code=404, detail="Answer key not found")
    
    # Update fields
    if update_data.model_answer is not None:
        answer_key.model_answer = update_data.model_answer
    
    if update_data.rubric is not None:
        answer_key.rubric = update_data.rubric
    
    if update_data.resource_citations is not None:
        answer_key.resource_citations = update_data.resource_citations
    
    if update_data.reviewed_by_faculty is not None:
        answer_key.reviewed_by_faculty = update_data.reviewed_by_faculty
    
    db.commit()
    db.refresh(answer_key)
    
    logger.info("Answer key updated", extra={
        "answer_key_id": str(answer_key_id),
        "faculty_id": str(current_user.id)
    })
    
    return AnswerKeyResponse.from_orm(answer_key)


@router.delete("/{answer_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_answer_key(
    answer_key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Delete an answer key"""
    
    answer_key = db.query(AnswerKey).filter(AnswerKey.id == answer_key_id).first()
    
    if not answer_key:
        raise HTTPException(status_code=404, detail="Answer key not found")
    
    db.delete(answer_key)
    db.commit()
    
    return None


@router.post("/question/{question_id}/generate", response_model=AnswerKeyResponse)
async def generate_single_answer_key(
    question_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Generate answer key for a single question"""
    
    # Verify question exists
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Generate answer key
    agent = AnswerKeyGeneratorAgent(db)
    answer_key = await agent.generate_answer_key(question_id)
    
    return AnswerKeyResponse.from_orm(answer_key)
