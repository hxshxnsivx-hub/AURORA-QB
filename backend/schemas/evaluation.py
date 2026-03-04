"""Pydantic schemas for evaluations"""

from pydantic import BaseModel, Field
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


class EvaluationSummaryResponse(BaseModel):
    """Schema for evaluation summary"""
    attempt_id: UUID
    total_score: float
    max_score: float
    percentage: float
    feedback_summary: str
    evaluations: List[EvaluationResponse]
