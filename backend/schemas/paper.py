"""Pydantic schemas for paper operations"""

from pydantic import BaseModel, Field, field_serializer
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime


class PaperConstraints(BaseModel):
    """Paper generation constraints"""
    total_marks: int = Field(..., ge=1, description="Total marks for the paper")
    mark_distribution: Dict[str, int] = Field(..., description="Distribution of marks")
    type_distribution: Optional[Dict[str, int]] = Field(None, description="Question type distribution")
    difficulty_mix: Optional[Dict[str, float]] = Field(None, description="Difficulty percentages")
    topic_coverage: Optional[Dict[str, int]] = Field(None, description="Minimum questions per topic")


class PaperGenerateRequest(BaseModel):
    """Request to generate papers"""
    subject_id: UUID
    constraints: PaperConstraints
    num_sets: int = Field(1, ge=1, le=10, description="Number of paper sets to generate")
    title_prefix: Optional[str] = Field("Exam Paper", description="Title prefix for papers")
    
    @field_serializer('subject_id')
    def serialize_subject_id(self, value: UUID) -> str:
        return str(value)


class QuestionInPaper(BaseModel):
    """Question in a paper"""
    id: UUID
    text: str
    marks: int
    type: str
    order: int
    
    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class PaperResponse(BaseModel):
    """Paper response"""
    id: UUID
    subject_id: UUID
    faculty_id: UUID
    title: str
    total_marks: int
    generation_date: datetime
    constraints: Dict
    questions_count: Optional[int] = None
    
    @field_serializer('id', 'subject_id', 'faculty_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class PaperDetailResponse(PaperResponse):
    """Detailed paper response with questions"""
    questions: List[QuestionInPaper]


class ConstraintValidationResponse(BaseModel):
    """Constraint validation result"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class PaperGenerationResponse(BaseModel):
    """Paper generation result"""
    task_id: str
    papers: List[PaperResponse]
    num_sets: int
    diversity_score: Optional[float] = None
