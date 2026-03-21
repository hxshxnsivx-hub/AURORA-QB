"""Unit tests for Roadmap Agent"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from agents.roadmap_agent import RoadmapAgent
from models.performance import Weakness, ConceptMastery
from models.academic import Subject, Unit, Topic, Concept
from models.roadmap import RoadmapTask
from models.user import User, UserRole


@pytest.fixture
def setup_roadmap_data(db: Session):
    """Setup test data for roadmap tests"""
    # Create subject
    subject = Subject(name="Math", code="MATH101")
    db.add(subject)
    db.commit()
    
    # Create unit and topic
    unit = Unit(name="Algebra", code="ALG", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic = Topic(name="Equations", unit_id=unit.id)
    db.add(topic)
    db.commit()
    
    # Create concept
    concept = Concept(name="Linear Equations", topic_id=topic.id, importance=0.8)
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
    
    # Create weakness
    weakness = Weakness(
        student_id=student.id,
        topic_id=topic.id,
        severity=0.7,
        mastery_score=0.3,
        recommended_resources=[]
    )
    db.add(weakness)
    db.commit()
    
    return {
        "subject": subject,
        "topic": topic,
        "concept": concept,
        "student": student,
        "weakness": weakness
    }


class TestRoadmapAgent:
    """Test suite for Roadmap Agent"""
    
    @pytest.mark.asyncio
    async def test_format_roadmap_update(self, db, setup_roadmap_data):
        """Test roadmap update formatting"""
        agent = RoadmapAgent(db)
        student = setup_roadmap_data["student"]
        weakness = setup_roadmap_data["weakness"]
        
        payload = await agent.format_roadmap_update(student.id, [weakness])
        
        assert "student_id" in payload
        assert "weaknesses" in payload
        assert len(payload["weaknesses"]) > 0
    
    @pytest.mark.asyncio
    async def test_receive_roadmap_tasks(self, db, setup_roadmap_data):
        """Test receiving roadmap tasks"""
        agent = RoadmapAgent(db)
        student = setup_roadmap_data["student"]
        concept = setup_roadmap_data["concept"]
        
        tasks = [
            {
                "id": "task-1",
                "concept_id": str(concept.id),
                "title": "Practice Linear Equations",
                "description": "Complete 10 problems",
                "resources": [],
                "completed": False
            }
        ]
        
        await agent.receive_roadmap_tasks(student.id, tasks)
        
        # Check task was created
        task = db.query(RoadmapTask).filter(
            RoadmapTask.student_id == student.id
        ).first()
        
        assert task is not None
        assert task.title == "Practice Linear Equations"
    
    @pytest.mark.asyncio
    async def test_mark_task_complete(self, db, setup_roadmap_data):
        """Test marking task as complete"""
        agent = RoadmapAgent(db)
        student = setup_roadmap_data["student"]
        concept = setup_roadmap_data["concept"]
        
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
        
        # Mark complete
        await agent.mark_task_complete(task.id, student.id)
        
        # Check task is completed
        db.refresh(task)
        assert task.completed is True
        assert task.completed_at is not None
