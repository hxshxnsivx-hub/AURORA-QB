from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum
from database import Base


class AgentTaskStatus(str, enum.Enum):
    """Agent task status enumeration"""
    QUEUED = "Queued"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AgentTask(Base):
    """Agent task model for multi-agent orchestration"""
    
    __tablename__ = "agent_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type = Column(String(100), nullable=False, index=True)
    status = Column(
        SQLEnum(AgentTaskStatus, name="agent_task_status"),
        nullable=False,
        default=AgentTaskStatus.QUEUED,
        index=True
    )
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON)
    error_message = Column(Text)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    def __repr__(self) -> str:
        return f"<AgentTask(id={self.id}, agent={self.agent_type}, status={self.status})>"
