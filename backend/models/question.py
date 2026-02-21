from sqlalchemy import Column, String, Integer, Float, Text, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
import enum
from database import Base


class QuestionBankStatus(str, enum.Enum):
    """Question bank processing status"""
    UPLOADED = "Uploaded"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class QuestionType(str, enum.Enum):
    """Question type enumeration"""
    MCQ = "MCQ"
    SHORT_ANSWER = "Short Answer"
    LONG_ANSWER = "Long Answer"
    NUMERICAL = "Numerical"
    TRUE_FALSE = "True/False"


class DifficultyLevel(str, enum.Enum):
    """Difficulty level enumeration"""
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class QuestionBank(Base):
    """Question bank model for uploaded question files"""
    
    __tablename__ = "question_banks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    status = Column(
        SQLEnum(QuestionBankStatus, name="question_bank_status"),
        nullable=False,
        default=QuestionBankStatus.UPLOADED,
        index=True
    )
    upload_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    processing_error = Column(Text)
    
    # Relationships
    questions = relationship("Question", back_populates="bank", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<QuestionBank(id={self.id}, file_name={self.file_name}, status={self.status})>"


class Question(Base):
    """Question model for individual questions"""
    
    __tablename__ = "questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_id = Column(
        UUID(as_uuid=True),
        ForeignKey("question_banks.id"),
        nullable=False,
        index=True
    )
    text = Column(Text, nullable=False)
    marks = Column(Integer, nullable=False, index=True)
    type = Column(
        SQLEnum(QuestionType, name="question_type"),
        nullable=False,
        index=True
    )
    difficulty = Column(
        SQLEnum(DifficultyLevel, name="difficulty_level"),
        nullable=False,
        index=True
    )
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), index=True)
    correct_answer = Column(Text)  # For MCQ/True-False
    embedding = Column(Vector(1536))  # OpenAI embedding dimension
    tags_confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    bank = relationship("QuestionBank", back_populates="questions")
    
    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.type}, marks={self.marks})>"
