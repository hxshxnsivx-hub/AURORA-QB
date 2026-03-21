"""
Pydantic schemas for question bank operations.
"""

from pydantic import BaseModel, Field, validator, field_serializer
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class QuestionBankStatus(str, Enum):
    """Question bank processing status"""
    UPLOADED = "Uploaded"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class QuestionType(str, Enum):
    """Question type enumeration"""
    MCQ = "MCQ"
    SHORT_ANSWER = "Short Answer"
    LONG_ANSWER = "Long Answer"
    NUMERICAL = "Numerical"
    TRUE_FALSE = "True/False"


class DifficultyLevel(str, Enum):
    """Difficulty level enumeration"""
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class QuestionBankUpload(BaseModel):
    """Schema for question bank upload"""
    subject_id: UUID = Field(..., description="Subject ID")
    file_name: str = Field(..., description="Original file name")
    file_size: int = Field(..., description="File size in bytes")
    
    @field_serializer('subject_id')
    def serialize_subject_id(self, value: UUID) -> str:
        return str(value)
    
    @validator('file_size')
    def validate_file_size(cls, v):
        """Validate file size (max 50MB)"""
        if v > 50 * 1024 * 1024:
            raise ValueError("File size must not exceed 50MB")
        return v


class QuestionBankResponse(BaseModel):
    """Schema for question bank response"""
    id: UUID
    subject_id: UUID
    faculty_id: UUID
    file_name: str
    file_size: int
    status: QuestionBankStatus
    upload_date: datetime
    processing_error: Optional[str] = None
    questions_count: Optional[int] = None
    
    @field_serializer('id', 'subject_id', 'faculty_id')
    def serialize_uuids(self, value: UUID) -> str:
        return str(value)
    
    class Config:
        from_attributes = True


class QuestionTagSuggestion(BaseModel):
    """Schema for LLM-suggested question tags"""
    marks: int = Field(..., ge=1, le=12, description="Question marks")
    type: QuestionType
    difficulty: DifficultyLevel
    topic: Optional[str] = Field(None, description="Suggested topic name")
    unit: Optional[str] = Field(None, description="Suggested unit name")


class QuestionCreate(BaseModel):
    """Schema for creating a question"""
    bank_id: UUID
    text: str = Field(..., min_length=10, description="Question text")
    marks: int = Field(..., ge=1, le=12)
    type: QuestionType
    difficulty: DifficultyLevel
    unit_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    correct_answer: Optional[str] = None
    
    @field_serializer('bank_id', 'unit_id', 'topic_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None


class QuestionUpdate(BaseModel):
    """Schema for updating question tags"""
    marks: Optional[int] = Field(None, ge=1, le=12)
    type: Optional[QuestionType] = None
    difficulty: Optional[DifficultyLevel] = None
    unit_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    correct_answer: Optional[str] = None
    tags_confirmed: Optional[bool] = None
    
    @field_serializer('unit_id', 'topic_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None


class QuestionResponse(BaseModel):
    """Schema for question response"""
    id: UUID
    bank_id: UUID
    text: str
    marks: int
    type: QuestionType
    difficulty: DifficultyLevel
    unit_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    correct_answer: Optional[str] = None
    tags_confirmed: bool
    created_at: datetime
    
    @field_serializer('id', 'bank_id', 'unit_id', 'topic_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None
    
    class Config:
        from_attributes = True


class BulkTagUpdate(BaseModel):
    """Schema for bulk tagging questions"""
    question_ids: List[UUID] = Field(..., min_items=1, description="List of question IDs")
    unit_id: Optional[UUID] = None
    topic_id: Optional[UUID] = None
    marks: Optional[int] = Field(None, ge=1, le=12)
    type: Optional[QuestionType] = None
    difficulty: Optional[DifficultyLevel] = None
    tags_confirmed: Optional[bool] = None
    
    @field_serializer('question_ids')
    def serialize_question_ids(self, value: List[UUID]) -> List[str]:
        return [str(v) for v in value]
    
    @field_serializer('unit_id', 'topic_id')
    def serialize_uuids(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None


class BulkTagResponse(BaseModel):
    """Schema for bulk tag update response"""
    updated_count: int
    failed_count: int
    failed_ids: List[UUID] = []
    
    @field_serializer('failed_ids')
    def serialize_failed_ids(self, value: List[UUID]) -> List[str]:
        return [str(v) for v in value]
