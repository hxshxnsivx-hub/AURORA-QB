from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Paper(Base):
    """Paper model for generated exam papers"""
    
    __tablename__ = "papers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    total_marks = Column(Integer, nullable=False)
    constraints = Column(JSON, nullable=False)  # PaperConstraints as JSON
    generation_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    paper_questions = relationship(
        "PaperQuestion",
        back_populates="paper",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Paper(id={self.id}, title={self.title}, total_marks={self.total_marks})>"


class PaperQuestion(Base):
    """Link table between papers and questions with ordering"""
    
    __tablename__ = "paper_questions"
    
    paper_id = Column(
        UUID(as_uuid=True),
        ForeignKey("papers.id"),
        primary_key=True,
        index=True
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        primary_key=True,
        index=True
    )
    order = Column(Integer, nullable=False)
    
    # Relationships
    paper = relationship("Paper", back_populates="paper_questions")
    
    def __repr__(self) -> str:
        return f"<PaperQuestion(paper={self.paper_id}, question={self.question_id}, order={self.order})>"
