"""Unit tests for Weakness Analyzer Agent"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from agents.weakness_analyzer_agent import WeaknessAnalyzerAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic, Concept
from models.question import QuestionBank
from models.paper import Paper, PaperQuestion
from models.attempt import Attempt
from models.evaluation import Evaluation
from models.performance import TopicPerformance, Weakness, ConceptMastery
from models.user import User, UserRole


@pytest.fixture
def setup_performance_data(db: Session):
    """Setup test data for performance analysis"""
    # Create subject
    subject = Subject(name="Math", code="MATH101")
    db.add(subject)
    db.commit()
    
    # Create unit and topics
    unit = Unit(name="Algebra", code="ALG", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic1 = Topic(name="Linear Equations", unit_id=unit.id)
    topic2 = Topic(name="Quadratic Equations", unit_id=unit.id)
    db.add_all([topic1, topic2])
    db.commit()
    
    # Create concepts
    concept1 = Concept(name="Solving Linear", topic_id=topic1.id, importance=0.8)
    concept2 = Concept(name="Solving Quadratic", topic_id=topic2.id, importance=0.9)
    db.add_all([concept1, concept2])
    db.commit()
    
    # Create users
    student = User(
        email="student@test.com",
        username="student",
        hashed_password="hashed",
        role=UserRole.STUDENT
    )
    faculty = User(
        email="faculty@test.com",
        username="faculty",
        hashed_password="hashed",
        role=UserRole.FACULTY
    )
    db.add_all([student, faculty])
    db.commit()
    
    # Create question bank
    bank = QuestionBank(
        subject_id=subject.id,
        title="Test Bank",
        file_path="test.pdf",
        status="completed"
    )
    db.add(bank)
    db.commit()
    
    # Create paper
    paper = Paper(
        subject_id=subject.id,
        faculty_id=faculty.id,
        title="Test Paper",
        total_marks=20,
        constraints={}
    )
    db.add(paper)
    db.commit()
    
    # Create questions
    q1 = Question(
        bank_id=bank.id,
        text="Linear question",
        marks=10,
        type=QuestionType.SHORT_ANSWER,
        difficulty=DifficultyLevel.MEDIUM,
        topic_id=topic1.id,
        tags_confirmed=True
    )
    q2 = Question(
        bank_id=bank.id,
        text="Quadratic question",
        marks=10,
        type=QuestionType.SHORT_ANSWER,
        difficulty=DifficultyLevel.HARD,
        topic_id=topic2.id,
        tags_confirmed=True
    )
    db.add_all([q1, q2])
    db.commit()
    
    # Add questions to paper
    pq1 = PaperQuestion(paper_id=paper.id, question_id=q1.id, order=1)
    pq2 = PaperQuestion(paper_id=paper.id, question_id=q2.id, order=2)
    db.add_all([pq1, pq2])
    db.commit()
    
    # Create attempt
    attempt = Attempt(
        paper_id=paper.id,
        student_id=student.id,
        status="evaluated"
    )
    db.add(attempt)
    db.commit()
    
    # Create evaluations (weak in topic2)
    eval1 = Evaluation(
        attempt_id=attempt.id,
        question_id=q1.id,
        score=8.0,  # 80% - good
        feedback="Good work",
        evaluated_by_llm=True
    )
    eval2 = Evaluation(
        attempt_id=attempt.id,
        question_id=q2.id,
        score=3.0,  # 30% - weak
        feedback="Needs improvement",
        evaluated_by_llm=True
    )
    db.add_all([eval1, eval2])
    db.commit()
    
    return {
        "subject": subject,
        "topic1": topic1,
        "topic2": topic2,
        "concept1": concept1,
        "concept2": concept2,
        "student": student,
        "faculty": faculty,
        "paper": paper,
        "attempt": attempt,
        "eval1": eval1,
        "eval2": eval2
    }


class TestWeaknessAnalyzerAgent:
    """Test suite for Weakness Analyzer Agent"""
    
    @pytest.mark.asyncio
    async def test_calculate_topic_performance(self, db, setup_performance_data):
        """Test topic performance calculation"""
        agent = WeaknessAnalyzerAgent(db)
        student_id = setup_performance_data["student"].id
        subject_id = setup_performance_data["subject"].id
        
        performances = await agent._calculate_topic_performance(student_id, subject_id)
        
        assert len(performances) == 2
        # Topic1 should have 80% (8/10)
        # Topic2 should have 30% (3/10)
    
    @pytest.mark.asyncio
    async def test_identify_weaknesses(self, db, setup_performance_data):
        """Test weakness identification"""
        agent = WeaknessAnalyzerAgent(db)
        student_id = setup_performance_data["student"].id
        subject_id = setup_performance_data["subject"].id
        
        # First analyze performance
        await agent.analyze_performance(student_id, subject_id)
        
        # Then identify weaknesses
        weaknesses = agent.identify_weaknesses(student_id, subject_id)
        
        # Should identify topic2 as weak (30% < 60%)
        assert len(weaknesses) >= 1
        weak_topic_ids = [w.topic_id for w in weaknesses]
        assert setup_performance_data["topic2"].id in weak_topic_ids
    
    @pytest.mark.asyncio
    async def test_calculate_severity(self, db):
        """Test severity calculation"""
        agent = WeaknessAnalyzerAgent(db)
        
        # 0% should have severity 1.0
        assert agent._calculate_severity(0.0) == 1.0
        
        # 60% should have severity 0.0
        assert agent._calculate_severity(0.6) == 0.0
        
        # 30% should have severity 0.5
        assert abs(agent._calculate_severity(0.3) - 0.5) < 0.01
    
    @pytest.mark.asyncio
    async def test_update_concept_mastery(self, db, setup_performance_data):
        """Test concept mastery update"""
        agent = WeaknessAnalyzerAgent(db)
        student_id = setup_performance_data["student"].id
        subject_id = setup_performance_data["subject"].id
        
        # First calculate topic performance
        await agent._calculate_topic_performance(student_id, subject_id)
        
        # Then update concept mastery
        await agent.update_concept_mastery(student_id, subject_id)
        
        # Check concept mastery was created
        masteries = db.query(ConceptMastery).filter(
            ConceptMastery.student_id == student_id
        ).all()
        
        assert len(masteries) >= 1
