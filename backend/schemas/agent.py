"""
Pydantic schemas for agent orchestration system.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TaskPriority(str, Enum):
    """Task priority levels"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatusEnum(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    agent_type: str = Field(..., description="Type of agent to process this task")
    payload: Dict[str, Any] = Field(..., description="Task-specific data")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority level"
    )


class TaskResponse(BaseModel):
    """Schema for task response"""
    task_id: str = Field(..., description="Unique task identifier")
    agent_type: str = Field(..., description="Agent type")
    status: TaskStatusEnum = Field(..., description="Current task status")
    priority: TaskPriority = Field(..., description="Task priority")
    payload: Dict[str, Any] = Field(..., description="Task payload")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")


class AgentStatusResponse(BaseModel):
    """Schema for agent status"""
    agent_type: str = Field(..., description="Agent type identifier")
    status: str = Field(..., description="Current agent status")
    tasks_processed: int = Field(..., description="Total tasks processed")
    tasks_failed: int = Field(..., description="Total tasks failed")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")
    last_error: Optional[str] = Field(None, description="Last error message")
    started_at: Optional[datetime] = Field(None, description="Agent start time")


class QueueStatsResponse(BaseModel):
    """Schema for queue statistics"""
    pending_high: int = Field(..., description="High priority pending tasks")
    pending_normal: int = Field(..., description="Normal priority pending tasks")
    pending_low: int = Field(..., description="Low priority pending tasks")
    pending_total: int = Field(..., description="Total pending tasks")
    processing: int = Field(..., description="Currently processing tasks")
    completed: int = Field(..., description="Completed tasks")
    failed: int = Field(..., description="Failed tasks")


class OrchestratorStatsResponse(BaseModel):
    """Schema for orchestrator statistics"""
    running: bool = Field(..., description="Whether orchestrator is running")
    num_agents: int = Field(..., description="Number of registered agents")
    num_workers: int = Field(..., description="Number of active workers")
    queue: QueueStatsResponse = Field(..., description="Queue statistics")
    agents: Dict[str, AgentStatusResponse] = Field(..., description="Agent statistics")


class EventPublish(BaseModel):
    """Schema for publishing an event"""
    event_type: str = Field(..., description="Event type/channel name")
    data: Dict[str, Any] = Field(..., description="Event data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class EventResponse(BaseModel):
    """Schema for event response"""
    event_type: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    metadata: Dict[str, Any] = Field(..., description="Event metadata")
    timestamp: datetime = Field(..., description="Event timestamp")
    num_subscribers: int = Field(..., description="Number of subscribers notified")
