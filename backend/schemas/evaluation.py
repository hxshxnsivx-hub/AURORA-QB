"""Pydantic schemas for evaluations"""

from pydantic import BaseModel, Field, field_serializer
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class EvaluationResponse(BaseModel):
    """Schema for evaluation response"""
    id: UUID
    attempt_id: UUID
    question_id: UUID
    score: float
    feedback: str
    evaluated_by_llm: bool
    overridden_by_faculty: bool
    created_at: datetime
    
    @field_serializer('id', 'attempt_id', 'question_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class EvaluationUpdate(BaseModel):
    """Schema for updating an evaluation"""
    score: Optional[float] = None
    feedback: Optional[str] = None
    overridden_by_faculty: Optional[bool] = None


class EvaluationTriggerRequest(BaseModel):
    """Schema for triggering evaluation"""
    attempt_id: UUID
    
    @field_serializer('attempt_id')
    def serialize_attempt_id(self, value: UUID) -> str:
        return str(value)


class EvaluationSummaryResponse(BaseModel):
    """Schema for evaluation summary"""
    attempt_id: UUID
    total_score: float
    max_score: float
    percentage: float
    feedback_summary: str
    evaluations: List[EvaluationResponse]
    
    @field_serializer('attempt_id')
    def serialize_attempt_id(self, value: UUID) -> str:
        return str(value)
