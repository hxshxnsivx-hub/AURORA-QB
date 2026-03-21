"""Pydantic schemas for roadmap management"""

from pydantic import BaseModel, field_serializer
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class RoadmapTaskResponse(BaseModel):
    """Schema for roadmap task response"""
    id: UUID
    student_id: UUID
    concept_id: Optional[UUID]
    external_id: Optional[str]
    title: str
    description: str
    resources: List[str]
    due_date: Optional[datetime]
    completed: bool
    completed_at: Optional[datetime]
    created_at: datetime
    
    @field_serializer('id', 'student_id', 'concept_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None
    
    class Config:
        from_attributes = True


class RoadmapTaskUpdate(BaseModel):
    """Schema for updating a roadmap task"""
    completed: Optional[bool] = None


class RoadmapUpdateRequest(BaseModel):
    """Schema for requesting roadmap update"""
    student_id: UUID
    subject_id: UUID
    
    @field_serializer('student_id', 'subject_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)


class RoadmapUpdateResponse(BaseModel):
    """Schema for roadmap update response"""
    id: UUID
    student_id: UUID
    payload: Dict[str, Any]
    sent_at: datetime
    acknowledged: bool
    
    @field_serializer('id', 'student_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class RoadmapTasksReceiveRequest(BaseModel):
    """Schema for receiving tasks from AURORA Learn"""
    student_id: UUID
    tasks: List[Dict[str, Any]]
    
    @field_serializer('student_id')
    def serialize_student_id(self, value: UUID) -> str:
        return str(value)
