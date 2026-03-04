"""Pydantic schemas for performance analysis"""

from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class TopicPerformanceResponse(BaseModel):
    """Schema for topic performance response"""
    id: UUID
    student_id: UUID
    topic_id: UUID
    total_score: float
    max_score: float
    percentage: float
    attempt_count: int
    last_attempt: Optional[datetime]
    
    class Config:
        from_attributes = True


class WeaknessResponse(BaseModel):
    """Schema for weakness response"""
    id: UUID
    student_id: UUID
    topic_id: UUID
    severity: float
    mastery_score: float
    recommended_resources: List[str]
    
    class Config:
        from_attributes = True


class ConceptMasteryResponse(BaseModel):
    """Schema for concept mastery response"""
    id: UUID
    student_id: UUID
    concept_id: UUID
    mastery_level: float
    last_updated: datetime
    
    class Config:
        from_attributes = True


class PerformanceAnalysisRequest(BaseModel):
    """Schema for requesting performance analysis"""
    student_id: UUID
    evaluation_id: UUID


class PerformanceAnalysisResponse(BaseModel):
    """Schema for comprehensive performance analysis"""
    student_id: UUID
    subject_id: UUID
    overall_percentage: float
    topic_performances: List[TopicPerformanceResponse]
    weaknesses: List[WeaknessResponse]
    weakness_count: int
