from sqlalchemy import Column, Text, Boolean, ForeignKey, DateTime, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class AnswerKey(Base):
    """Answer key model for question model answers and rubrics"""
    
    __tablename__ = "answer_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        nullable=False,
        unique=True,
        index=True
    )
    model_answer = Column(Text, nullable=False)
    rubric = Column(JSON, nullable=False)  # GradingRubric as JSON
    resource_citations = Column(ARRAY(UUID(as_uuid=True)), default=[])
    reviewed_by_faculty = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<AnswerKey(id={self.id}, question_id={self.question_id}, reviewed={self.reviewed_by_faculty})>"
