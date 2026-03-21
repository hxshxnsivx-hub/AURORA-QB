"""Unit and property tests for Knowledge Graph"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from utils.knowledge_graph import KnowledgeGraph
from models.academic import Subject, Unit, Topic, Concept, ConceptPrerequisite
from models.question import Question, QuestionType, DifficultyLevel, QuestionBank
from models.performance import ConceptMastery
from models.user import User, UserRole


@pytest.fixture
def setup_kg_data(db: Session):
    """Setup test data for knowledge graph"""
    # Create subject
    subject = Subject(name="Math", code="MATH101")
    db.add(subject)
    db.commit()
    
    # Create unit and topics
    unit = Unit(name="Algebra", code="ALG", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic1 = Topic(name="Linear", unit_id=unit.id)
    topic2 = Topic(name="Quadratic", unit_id=unit.id)
    db.add_all([topic1, topic2])
    db.commit()
    
    # Create concepts
    concept1 = Concept(name="Basic Linear", topic_id=topic1.id, importance=0.7)
    concept2 = Concept(name="Advanced Linear", topic_id=topic1.id, importance=0.9)
    db.add_all([concept1, concept2])
    db.commit()
    
    # Create student
    student = User(
        email="student@test.com",
        username="student",
        hashed_password="hashed",
        role=UserRole.STUDENT
    )
    db.add(student)
    db.commit()
    
    return {
        "subject": subject,
        "topic1": topic1,
        "concept1": concept1,
        "concept2": concept2,
        "student": student
    }


class TestKnowledgeGraph:
    """Test suite for Knowledge Graph"""
    
    def test_create_prerequisite_relationship(self, db, setup_kg_data):
        """Test creating prerequisite relationship"""
        kg = KnowledgeGraph(db)
        concept1 = setup_kg_data["concept1"]
        concept2 = setup_kg_data["concept2"]
        
        kg.create_prerequisite_relationship(concept2.id, concept1.id, 0.8)
        
        # Check relationship exists
        prereq = db.query(ConceptPrerequisite).filter(
            ConceptPrerequisite.concept_id == concept2.id,
            ConceptPrerequisite.prerequisite_id == concept1.id
        ).first()
        
        assert prereq is not None
        assert prereq.strength == 0.8
    
    def test_get_concept_prerequisites(self, db, setup_kg_data):
        """Test getting concept prerequisites"""
        kg = KnowledgeGraph(db)
        concept1 = setup_kg_data["concept1"]
        concept2 = setup_kg_data["concept2"]
        
        # Create prerequisite
        kg.create_prerequisite_relationship(concept2.id, concept1.id, 0.9)
        
        # Get prerequisites
        prereqs = kg.get_concept_prerequisites(concept2.id)
        
        assert len(prereqs) == 1
        assert prereqs[0]["concept_id"] == str(concept1.id)
    
    def test_get_weak_concepts_with_strong_prerequisites(self, db, setup_kg_data):
        """Test finding weak concepts with strong prerequisites"""
        kg = KnowledgeGraph(db)
        student = setup_kg_data["student"]
        concept1 = setup_kg_data["concept1"]
        concept2 = setup_kg_data["concept2"]
        
        # Create prerequisite relationship
        kg.create_prerequisite_relationship(concept2.id, concept1.id, 1.0)
        
        # Student is strong in concept1, weak in concept2
        mastery1 = ConceptMastery(
            student_id=student.id,
            concept_id=concept1.id,
            mastery_level=0.8
        )
        mastery2 = ConceptMastery(
            student_id=student.id,
            concept_id=concept2.id,
            mastery_level=0.3
        )
        db.add_all([mastery1, mastery2])
        db.commit()
        
        # Find weak concepts with strong prerequisites
        results = kg.get_weak_concepts_with_strong_prerequisites(student.id)
        
        assert len(results) >= 1
        assert any(r["concept_id"] == str(concept2.id) for r in results)
