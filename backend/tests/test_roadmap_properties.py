"""Property-based tests for Roadmap Agent"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session

from agents.roadmap_agent import RoadmapAgent
from models.performance import Weakness, ConceptMastery
from models.academic import Subject, Unit, Topic, Concept
from models.roadmap import RoadmapTask
from models.user import User, UserRole


@pytest.fixture
def setup_test_data(db: Session):
    """Setup test data for property tests"""
    # Create subject
    subject = Subject(name="Test Subject", code="TEST101")
    db.add(subject)
    db.commit()
    
    # Create unit and topic
    unit = Unit(name="Test Unit", code="TU", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic = Topic(name="Test Topic", unit_id=unit.id)
    db.add(topic)
    db.commit()
    
    # Create concept
    concept = Concept(name="Test Concept", topic_id=topic.id, importance=0.8)
    db.add(concept)
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
        "topic": topic,
        "concept": concept,
        "student": student
    }


class TestRoadmapAgentProperties:
    """Property-based tests for Roadmap Agent"""
    
    @pytest.mark.asyncio
    @given(
        severity=st.floats(min_value=0, max_value=1),
        mastery_score=st.floats(min_value=0, max_value=1)
    )
    @settings(max_examples=15, deadline=5000)
    async def test_property_55_roadmap_update_format_completeness(
        self, db, setup_test_data, severity, mastery_score
    ):
        """
        **Validates: Requirements 12.3**
        
        Property 55: Roadmap Update Format Completeness
        
        For any roadmap update, the payload should include concept IDs,
        mastery scores, and recommended resources for all weaknesses.
        """
        agent = RoadmapAgent(db)
        student = setup_test_data["student"]
        topic = setup_test_data["topic"]
        concept = setup_test_data["concept"]
        
        # Create weakness
        weakness = Weakness(
            student_id=student.id,
            topic_id=topic.id,
            severity=severity,
            mastery_score=mastery_score,
            recommended_resources=["resource-1", "resource-2"]
        )
        db.add(weakness)
        db.commit()
        
        # Create concept mastery
        mastery = ConceptMastery(
            student_id=student.id,
            concept_id=concept.id,
            mastery_level=mastery_score
        )
        db.add(mastery)
        db.commit()
        
        # Format roadmap update
        payload = await agent.format_roadmap_update(student.id, [weakness])
        
        # Check completeness
        assert "student_id" in payload
        assert "weaknesses" in payload
        assert "timestamp" in payload
        
        if len(payload["weaknesses"]) > 0:
            weakness_data = payload["weaknesses"][0]
            assert "concept_id" in weakness_data
            assert "mastery_score" in weakness_data
            assert "recommended_resources" in weakness_data
            assert "severity" in weakness_data
    
    @pytest.mark.asyncio
    @given(initial_mastery=st.floats(min_value=0, max_value=0.9))
    @settings(max_examples=15, deadline=5000)
    async def test_property_57_task_completion_mastery_update(
        self, db, setup_test_data, initial_mastery
    ):
        """
        **Validates: Requirements 12.7**
        
        Property 57: Task Completion Mastery Update
        
        For any completed roadmap task, the associated concept's mastery
        score should be increased.
        """
        agent = RoadmapAgent(db)
        student = setup_test_data["student"]
        concept = setup_test_data["concept"]
        
        # Create initial mastery
        mastery = ConceptMastery(
            student_id=student.id,
            concept_id=concept.id,
            mastery_level=initial_mastery
        )
        db.add(mastery)
        db.commit()
        
        # Create task
        task = RoadmapTask(
            student_id=student.id,
            concept_id=concept.id,
            title="Test Task",
            description="Test",
            resources=[],
            completed=False
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Mark task complete
        await agent.mark_task_complete(task.id, student.id)
        
        # Check mastery increased
        db.refresh(mastery)
        assert mastery.mastery_level > initial_mastery
        assert mastery.mastery_level <= 1.0
