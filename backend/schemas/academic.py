from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SubjectCreate(BaseModel):
    """Schema for creating a subject"""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Data Structures and Algorithms",
                "code": "CS201",
                "description": "Introduction to fundamental data structures and algorithms"
            }
        }


class SubjectResponse(BaseModel):
    """Schema for subject response"""
    id: str
    name: str
    code: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class SubjectUpdate(BaseModel):
    """Schema for updating a subject"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None


class UnitCreate(BaseModel):
    """Schema for creating a unit"""
    subject_id: str
    name: str = Field(..., min_length=1, max_length=255)
    order: int = Field(..., ge=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "subject_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Arrays and Linked Lists",
                "order": 1
            }
        }


class UnitResponse(BaseModel):
    """Schema for unit response"""
    id: str
    subject_id: str
    name: str
    order: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class UnitUpdate(BaseModel):
    """Schema for updating a unit"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    order: Optional[int] = Field(None, ge=1)


class TopicCreate(BaseModel):
    """Schema for creating a topic"""
    unit_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "unit_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Dynamic Arrays",
                "description": "Resizable arrays with amortized O(1) append"
            }
        }


class TopicResponse(BaseModel):
    """Schema for topic response"""
    id: str
    unit_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TopicUpdate(BaseModel):
    """Schema for updating a topic"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class ConceptCreate(BaseModel):
    """Schema for creating a concept"""
    topic_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Array Indexing",
                "description": "Accessing elements by index in O(1) time",
                "importance": 0.8
            }
        }


class ConceptResponse(BaseModel):
    """Schema for concept response"""
    id: str
    topic_id: str
    name: str
    description: Optional[str]
    importance: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConceptUpdate(BaseModel):
    """Schema for updating a concept"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
