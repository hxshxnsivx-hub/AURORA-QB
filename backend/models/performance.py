from sqlalchemy import Column, Float, Integer, ForeignKey, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class TopicPerformance(Base):
    """Topic performance model for student performance tracking"""
    
    __tablename__ = "topic_performance"
    
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
        index=True
    )
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id"),
        primary_key=True,
        index=True
    )
    total_score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=False, default=0.0)
    percentage = Column(Float, nullable=False, default=0.0)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_attempt = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<TopicPerformance(student={self.student_id}, topic={self.topic_id}, percentage={self.percentage})>"


class Weakness(Base):
    """Weakness model for identified student weaknesses"""
    
    __tablename__ = "weaknesses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False, index=True)
    severity = Column(Float, nullable=False)  # 0-1 scale
    mastery_score = Column(Float, nullable=False)  # 0-1 scale
    recommended_resources = Column(ARRAY(UUID(as_uuid=True)), default=[])
    identified_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Weakness(student={self.student_id}, concept={self.concept_id}, severity={self.severity})>"


class ConceptMastery(Base):
    """Concept mastery model for student concept proficiency tracking"""
    
    __tablename__ = "concept_mastery"
    
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
        index=True
    )
    concept_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id"),
        primary_key=True,
        index=True
    )
    mastery_level = Column(Float, nullable=False, default=0.0)  # 0-1 scale
    last_updated = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<ConceptMastery(student={self.student_id}, concept={self.concept_id}, level={self.mastery_level})>"
