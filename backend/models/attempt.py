from sqlalchemy import Column, Text, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from database import Base


class AttemptStatus(str, enum.Enum):
    """Attempt status enumeration"""
    IN_PROGRESS = "In Progress"
    SUBMITTED = "Submitted"
    EVALUATED = "Evaluated"


class Attempt(Base):
    """Attempt model for student exam attempts"""
    
    __tablename__ = "attempts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False, index=True)
    status = Column(
        SQLEnum(AttemptStatus, name="attempt_status"),
        nullable=False,
        default=AttemptStatus.IN_PROGRESS,
        index=True
    )
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    submit_time = Column(DateTime)
    
    # Relationships
    answers = relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Attempt(id={self.id}, student_id={self.student_id}, status={self.status})>"


class StudentAnswer(Base):
    """Student answer model for individual question responses"""
    
    __tablename__ = "student_answers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("attempts.id"),
        nullable=False,
        index=True
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        nullable=False,
        index=True
    )
    answer_text = Column(Text, nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    attempt = relationship("Attempt", back_populates="answers")
    
    def __repr__(self) -> str:
        return f"<StudentAnswer(id={self.id}, attempt_id={self.attempt_id}, question_id={self.question_id})>"
