from sqlalchemy import Column, Text, Integer, Float, Boolean, ForeignKey, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from database import Base


class EvaluatedBy(str, enum.Enum):
    """Evaluator type enumeration"""
    SYSTEM = "System"
    FACULTY = "Faculty"


class Evaluation(Base):
    """Evaluation model for graded attempts"""
    
    __tablename__ = "evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attempts.id"),
        nullable=False,
        unique=True,
        index=True
    )
    total_score = Column(Float, nullable=False)
    max_score = Column(Integer, nullable=False)
    evaluated_by = Column(
        SQLEnum(EvaluatedBy, name="evaluated_by"),
        nullable=False,
        default=EvaluatedBy.SYSTEM
    )
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    question_evaluations = relationship(
        "QuestionEvaluation",
        back_populates="evaluation",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, total_score={self.total_score}/{self.max_score})>"


class QuestionEvaluation(Base):
    """Question evaluation model for per-question grading"""
    
    __tablename__ = "question_evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id"),
        nullable=False,
        index=True
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )
    awarded_score = Column(Float, nullable=False)
    max_score = Column(Integer, nullable=False)
    feedback = Column(Text, nullable=False)
    criterion_scores = Column(JSON, nullable=False)  # List of CriterionScore as JSON
    overridden = Column(Boolean, nullable=False, default=False)
    overridden_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    overridden_at = Column(DateTime)
    
    # Relationships
    evaluation = relationship("Evaluation", back_populates="question_evaluations")
    
    def __repr__(self) -> str:
        return f"<QuestionEvaluation(id={self.id}, score={self.awarded_score}/{self.max_score})>"
