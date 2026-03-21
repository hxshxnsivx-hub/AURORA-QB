"""Pydantic schemas for resources"""

from pydantic import BaseModel, field_serializer
from typing import Optional
from uuid import UUID
from datetime import datetime


class ResourceResponse(BaseModel):
    """Schema for resource response"""
    id: UUID
    title: str
    file_path: str
    resource_type: str
    upload_date: datetime
    
    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class ResourceUploadResponse(BaseModel):
    """Schema for resource upload response"""
    id: UUID
    title: str
    file_path: str
    resource_type: str
    
    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)


class ResourceSearchRequest(BaseModel):
    """Schema for resource search request"""
    query: str
    min_similarity: float = 0.5
    limit: int = 10


class ResourceSearchResponse(BaseModel):
    """Schema for resource search response"""
    id: UUID
    title: str
    resource_type: str
    similarity_score: float
    
    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)
