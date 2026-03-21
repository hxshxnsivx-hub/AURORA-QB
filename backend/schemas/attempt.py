"""Pydantic schemas for exam attempts"""

from pydantic import BaseModel, field_serializer
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class AttemptStartRequest(BaseModel):
    """Schema for starting an attempt"""
    paper_id: UUID
    
    @field_serializer('paper_id')
    def serialize_paper_id(self, value: UUID) -> str:
        return str(value)


class AttemptResponse(BaseModel):
    """Schema for attempt response"""
    id: UUID
    paper_id: UUID
    student_id: UUID
    start_time: datetime
    submit_time: Optional[datetime]
    status: str
    total_score: Optional[float]
    
    @field_serializer('id', 'paper_id', 'student_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class AnswerSaveRequest(BaseModel):
    """Schema for saving an answer"""
    question_id: UUID
    answer_text: str
    
    @field_serializer('question_id')
    def serialize_question_id(self, value: UUID) -> str:
        return str(value)


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
    
    @field_serializer('id', 'paper_id', 'student_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
