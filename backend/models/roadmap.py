from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class RoadmapUpdate(Base):
    """Roadmap update model for AURORA Learn integration"""
    
    __tablename__ = "roadmap_updates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    weaknesses = Column(JSON, nullable=False)  # List of Weakness data as JSON
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(DateTime)
    
    def __repr__(self) -> str:
        return f"<RoadmapUpdate(id={self.id}, student={self.student_id}, acknowledged={self.acknowledged})>"


class RoadmapTask(Base):
    """Roadmap task model for personalized learning tasks"""
    
    __tablename__ = "roadmap_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    resources = Column(ARRAY(UUID(as_uuid=True)), default=[])
    due_date = Column(DateTime)
    completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<RoadmapTask(id={self.id}, title={self.title}, completed={self.completed})>"
