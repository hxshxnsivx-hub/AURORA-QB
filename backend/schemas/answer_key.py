"""Pydantic schemas for answer keys and grading rubrics"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime


class RubricCriterion(BaseModel):
    """Single criterion in a grading rubric"""
    description: str
    points: float


class GradingRubricSchema(BaseModel):
    """Grading rubric structure"""
    criteria: List[RubricCriterion]


class AnswerKeyCreate(BaseModel):
    """Schema for creating an answer key"""
    question_id: UUID
    model_answer: str
    rubric: Dict
    resource_citations: List[str] = []


class AnswerKeyUpdate(BaseModel):
    """Schema for updating an answer key"""
    model_answer: Optional[str] = None
    rubric: Optional[Dict] = None
    resource_citations: Optional[List[str]] = None
    reviewed_by_faculty: Optional[bool] = None


class AnswerKeyResponse(BaseModel):
    """Schema for answer key response"""
    id: UUID
    question_id: UUID
    model_answer: str
    rubric: Dict
    resource_citations: List[str]
    reviewed_by_faculty: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AnswerKeyGenerationRequest(BaseModel):
    """Schema for requesting answer key generation"""
    paper_id: UUID


class AnswerKeyGenerationResponse(BaseModel):
    """Schema for answer key generation response"""
    task_id: str
    status: str
    message: str


class AnswerKeyBulkResponse(BaseModel):
    """Schema for bulk answer key generation response"""
    paper_id: UUID
    generated_count: int
    total_questions: int
    answer_keys: List[AnswerKeyResponse]
