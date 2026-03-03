"""API endpoints for knowledge graph operations"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from utils.knowledge_graph import KnowledgeGraph
from schemas.knowledge_graph import (
    PrerequisiteCreateRequest,
    ConceptQuestionsResponse,
    PrerequisiteResponse,
    WeakConceptResponse,
    GraphVisualizationResponse
)
from utils.logger import logger


router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.post("/prerequisites")
async def create_prerequisite(
    request: PrerequisiteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Create a prerequisite relationship between concepts"""
    
    kg = KnowledgeGraph(db)
    kg.create_prerequisite_relationship(
        request.concept_id,
        request.prerequisite_id,
        request.strength
    )
    
    return {"status": "created"}


@router.get("/concepts/{concept_id}/questions", response_model=ConceptQuestionsResponse)
async def get_concept_questions(
    concept_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all questions covering a concept"""
    
    kg = KnowledgeGraph(db)
    questions = kg.get_questions_covering_concept(concept_id)
    
    return ConceptQuestionsResponse(
        concept_id=concept_id,
        question_count=len(questions),
        questions=[
            {
                "id": str(q.id),
                "text": q.text,
                "marks": q.marks,
                "type": q.type.value
            }
            for q in questions
        ]
    )


@router.get("/concepts/{concept_id}/prerequisites", response_model=List[PrerequisiteResponse])
async def get_prerequisites(
    concept_id: UUID,
    min_strength: float = 0.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get prerequisites for a concept"""
    
    kg = KnowledgeGraph(db)
    prereqs = kg.get_concept_prerequisites(concept_id, min_strength)
    
    return [PrerequisiteResponse(**p) for p in prereqs]


@router.get("/students/{student_id}/weak-with-strong-prereqs", response_model=List[WeakConceptResponse])
async def get_weak_concepts_with_strong_prerequisites(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get concepts where student is weak but has mastered prerequisites"""
    
    # Check permissions
    if current_user.id != student_id and current_user.role not in [UserRole.FACULTY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    kg = KnowledgeGraph(db)
    results = kg.get_weak_concepts_with_strong_prerequisites(student_id)
    
    return [WeakConceptResponse(**r) for r in results]


@router.get("/subjects/{subject_id}/visualization", response_model=GraphVisualizationResponse)
async def get_graph_visualization(
    subject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get knowledge graph visualization data"""
    
    kg = KnowledgeGraph(db)
    graph_data = kg.visualize_concept_graph(subject_id)
    
    return GraphVisualizationResponse(**graph_data)
