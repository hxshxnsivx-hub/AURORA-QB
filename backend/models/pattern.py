from sqlalchemy import Column, Float, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class Pattern(Base):
    """Pattern model for learned exam patterns"""
    
    __tablename__ = "patterns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Distribution data stored as JSON
    mark_distribution = Column(JSON, nullable=False)  # {marks: frequency}
    type_distribution = Column(JSON, nullable=False)  # {type: percentage}
    topic_weights = Column(JSON, nullable=False)  # {topic_id: weight}
    difficulty_by_marks = Column(JSON, nullable=False)  # {marks: {difficulty: percentage}}
    
    confidence = Column(Float, nullable=False, default=0.0)  # 0-1 scale
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<Pattern(id={self.id}, subject_id={self.subject_id}, confidence={self.confidence})>"
