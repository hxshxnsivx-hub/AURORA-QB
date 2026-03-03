"""API endpoints for performance analysis and weakness identification"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.performance import TopicPerformance, Weakness, ConceptMastery
from schemas.performance import (
    TopicPerformanceResponse,
    WeaknessResponse,
    ConceptMasteryResponse,
    PerformanceAnalysisRequest,
    PerformanceAnalysisResponse
)
from agents.task_queue import TaskQueue
from agents.weakness_analyzer_agent import WeaknessAnalyzerAgent
from utils.logger import logger


router = APIRouter(prefix="/performance", tags=["performance"])


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_performance_analysis(
    request: PerformanceAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger performance analysis for a student"""
    
    # Check permissions
    if current_user.id != request.student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Queue analysis task
    task_queue = TaskQueue()
    task_id = await task_queue.enqueue_task(
        agent_type="weakness_analyzer",
        payload={
            "student_id": str(request.student_id),
            "evaluation_id": str(request.evaluation_id)
        },
        priority=2
    )
    
    logger.info("Performance analysis queued", extra={
        "task_id": task_id,
        "student_id": str(request.student_id)
    })
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Performance analysis started"
    }


@router.get("/student/{student_id}/topics", response_model=List[TopicPerformanceResponse])
async def get_topic_performance(
    student_id: UUID,
    subject_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get topic-wise performance for a student"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = db.query(TopicPerformance).filter(
        TopicPerformance.student_id == student_id
    )
    
    if subject_id:
        from models.academic import Topic
        query = query.join(Topic).join(Topic.unit).filter(
            Topic.unit.has(subject_id=subject_id)
        )
    
    performances = query.all()
    
    return [TopicPerformanceResponse.from_orm(p) for p in performances]


@router.get("/student/{student_id}/weaknesses", response_model=List[WeaknessResponse])
async def get_weaknesses(
    student_id: UUID,
    subject_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get weaknesses for a student"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    agent = WeaknessAnalyzerAgent(db)
    
    if subject_id:
        weaknesses = agent.identify_weaknesses(student_id, subject_id)
    else:
        weaknesses = db.query(Weakness).filter(
            Weakness.student_id == student_id
        ).order_by(Weakness.severity.desc()).all()
    
    return [WeaknessResponse.from_orm(w) for w in weaknesses]


@router.get("/student/{student_id}/concepts", response_model=List[ConceptMasteryResponse])
async def get_concept_mastery(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get concept mastery levels for a student"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    masteries = db.query(ConceptMastery).filter(
        ConceptMastery.student_id == student_id
    ).order_by(ConceptMastery.mastery_level.asc()).all()
    
    return [ConceptMasteryResponse.from_orm(m) for m in masteries]


@router.get("/student/{student_id}/summary", response_model=PerformanceAnalysisResponse)
async def get_performance_summary(
    student_id: UUID,
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive performance summary"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    agent = WeaknessAnalyzerAgent(db)
    
    # Get topic performances
    topic_perfs = db.query(TopicPerformance).join(TopicPerformance.topic).join(
        TopicPerformance.topic.unit
    ).filter(
        TopicPerformance.student_id == student_id,
        TopicPerformance.topic.unit.has(subject_id=subject_id)
    ).all()
    
    # Get weaknesses
    weaknesses = agent.identify_weaknesses(student_id, subject_id)
    
    # Calculate overall performance
    if topic_perfs:
        total_score = sum(p.total_score for p in topic_perfs)
        max_score = sum(p.max_score for p in topic_perfs)
        overall_percentage = (total_score / max_score * 100) if max_score > 0 else 0
    else:
        overall_percentage = 0
    
    return PerformanceAnalysisResponse(
        student_id=student_id,
        subject_id=subject_id,
        overall_percentage=overall_percentage,
        topic_performances=[TopicPerformanceResponse.from_orm(p) for p in topic_perfs],
        weaknesses=[WeaknessResponse.from_orm(w) for w in weaknesses],
        weakness_count=len(weaknesses)
    )
