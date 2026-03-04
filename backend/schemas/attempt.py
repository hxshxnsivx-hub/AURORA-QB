"""Pydantic schemas for exam attempts"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class AttemptStartRequest(BaseModel):
    """Schema for starting an attempt"""
    paper_id: UUID


class AttemptResponse(BaseModel):
    """Schema for attempt response"""
    id: UUID
    paper_id: UUID
    student_id: UUID
    start_time: datetime
    submit_time: Optional[datetime]
    status: str
    total_score: Optional[float]
    
    class Config:
        from_attributes = True


class AnswerSaveRequest(BaseModel):
    """Schema for saving an answer"""
    question_id: UUID
    answer_text: str


class AnswerSubmitRequest(BaseModel):
    """Schema for submitting attempt"""
    pass  # No additional data needed


class AttemptDetailResponse(BaseModel):
    """Schema for detailed attempt with answers"""
    id: UUID
    paper_id: UUID
    student_id: UUID
    start_time: datetime
    submit_time: Optional[datetime]
    status: str
    total_score: Optional[float]
    answers: List[Dict[str, Any]]
