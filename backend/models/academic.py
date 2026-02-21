from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base


class Subject(Base):
    """Subject model representing academic subjects"""
    
    __tablename__ = "subjects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    units = relationship("Unit", back_populates="subject", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Subject(id={self.id}, code={self.code}, name={self.name})>"


class Unit(Base):
    """Unit model representing units/chapters within a subject"""
    
    __tablename__ = "units"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    order = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    subject = relationship("Subject", back_populates="units")
    topics = relationship("Topic", back_populates="unit", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Unit(id={self.id}, name={self.name}, order={self.order})>"


class Topic(Base):
    """Topic model representing topics within a unit"""
    
    __tablename__ = "topics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    unit = relationship("Unit", back_populates="topics")
    concepts = relationship("Concept", back_populates="topic", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, name={self.name})>"


class Concept(Base):
    """Concept model representing specific concepts within a topic"""
    
    __tablename__ = "concepts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    importance = Column(Float, nullable=False, default=0.5)  # 0-1 scale
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic", back_populates="concepts")
    
    def __repr__(self) -> str:
        return f"<Concept(id={self.id}, name={self.name}, importance={self.importance})>"


class ConceptPrerequisite(Base):
    """Model representing prerequisite relationships between concepts"""
    
    __tablename__ = "concept_prerequisites"
    
    concept_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id"),
        primary_key=True,
        index=True
    )
    prerequisite_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id"),
        primary_key=True,
        index=True
    )
    strength = Column(Float, nullable=False, default=1.0)  # 0-1 scale
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<ConceptPrerequisite(concept={self.concept_id}, prerequisite={self.prerequisite_id})>"
