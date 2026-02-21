"""
Pydantic schemas for agent API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

from models.agent import AgentTaskStatus, AgentType


class AgentTaskResponse(BaseModel):
    """Agent task response schema"""
    
    id: int
    agent_type: AgentType
    status: AgentTaskStatus
    priority: int
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AgentStatsResponse(BaseModel):
    """Agent orchestrator statistics"""
    
    running: bool
    workers: Dict[str, int] = Field(
        description="Worker pool statistics (total, active)"
    )
    agents: Dict[str, Any] = Field(
        description="Registered agents information"
    )
    queues: Dict[str, int] = Field(
        description="Queue statistics"
    )


class QueueStatsResponse(BaseModel):
    """Queue statistics"""
    
    main_queue: int = Field(description="Number of tasks in main queue")
    processing_queue: int = Field(description="Number of tasks being processed")
    dead_letter_queue: int = Field(description="Number of failed tasks in DLQ")


class RetryTaskRequest(BaseModel):
    """Request to retry a task"""
    
    max_attempts: Optional[int] = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts"
    )
    initial_delay: Optional[float] = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Initial delay in seconds"
    )


class CreateTaskRequest(BaseModel):
    """Request to create a new agent task"""
    
    agent_type: AgentType
    input_data: Dict[str, Any]
    priority: int = Field(default=0, ge=0, le=10)


class CreateTaskResponse(BaseModel):
    """Response after creating a task"""
    
    task_id: int
    agent_type: AgentType
    status: AgentTaskStatus
    created_at: datetime
