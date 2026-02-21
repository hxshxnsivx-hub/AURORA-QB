from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FileUploadResponse(BaseModel):
    """Schema for file upload response"""
    file_id: str
    file_key: str
    file_name: str
    file_size: int
    checksum: str
    upload_date: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_key": "question-banks/20240115/123e4567.pdf",
                "file_name": "sample_questions.pdf",
                "file_size": 1024000,
                "checksum": "5d41402abc4b2a76b9719d911017c592",
                "upload_date": "2024-01-15T10:30:00"
            }
        }


class FileDownloadResponse(BaseModel):
    """Schema for file download URL response"""
    download_url: str
    expires_in: int = Field(description="URL expiration time in seconds")
    file_name: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "download_url": "https://storage.example.com/...",
                "expires_in": 3600,
                "file_name": "sample_questions.pdf"
            }
        }


class FileMetadata(BaseModel):
    """Schema for file metadata"""
    file_id: str
    file_key: str
    file_name: str
    file_size: int
    checksum: str
    content_type: str
    upload_date: datetime
    is_deleted: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_key": "question-banks/20240115/123e4567.pdf",
                "file_name": "sample_questions.pdf",
                "file_size": 1024000,
                "checksum": "5d41402abc4b2a76b9719d911017c592",
                "content_type": "application/pdf",
                "upload_date": "2024-01-15T10:30:00",
                "is_deleted": false
            }
        }


class FileVersionResponse(BaseModel):
    """Schema for file version response"""
    version_key: str
    original_key: str
    version_timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "version_key": "question-banks/20240115/123e4567_v456.pdf",
                "original_key": "question-banks/20240115/123e4567.pdf",
                "version_timestamp": "2024-01-15T11:30:00"
            }
        }
