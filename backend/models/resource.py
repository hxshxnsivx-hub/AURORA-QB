from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
from database import Base


class Resource(Base):
    """Resource model for educational materials"""
    
    __tablename__ = "resources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embedding dimension
    upload_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, title={self.title}, type={self.file_type})>"


class ResourceTopicLink(Base):
    """Link table between resources and topics"""
    
    __tablename__ = "resource_topic_links"
    
    resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resources.id"),
        primary_key=True,
        index=True
    )
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id"),
        primary_key=True,
        index=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ResourceTopicLink(resource={self.resource_id}, topic={self.topic_id})>"


class QuestionResourceLink(Base):
    """Link table between questions and resources with relevance score"""
    
    __tablename__ = "question_resource_links"
    
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        primary_key=True,
        index=True
    )
    resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resources.id"),
        primary_key=True,
        index=True
    )
    relevance_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<QuestionResourceLink(question={self.question_id}, resource={self.resource_id})>"
