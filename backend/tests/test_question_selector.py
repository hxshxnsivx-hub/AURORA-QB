"""Unit tests for Question Selector Agent"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from agents.question_selector_agent import QuestionSelectorAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic
from models.question import QuestionBank
from models.pattern import Pattern
from models.paper import Paper, PaperQuestion
from models.user import User, UserRole


@pytest.fixture
def subject(db: Session):
    """Create test subject"""
    subject = Subject(name="Mathematics", code="MATH101")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@pytest.fixture
def topic(db: Session, subject):
    """Create test topic"""
    unit = Unit(name="Algebra", code="ALG", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic = Topic(name="Linear Equations", unit_id=unit.id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@pytest.fixture
def question_bank(db: Session, subject):
    """Create test question bank"""
    bank = QuestionBank(
        subject_id=subject.id,
        title="Test Bank",
        file_path="test.pdf",
        status="completed"
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


@pytest.fixture
def questions(db: Session, question_bank, topic):
    """Create test questions"""
    questions = []
    
    # Create 2-mark questions
    for i in range(15):
        q = Question(
            bank_id=question_bank.id,
            text=f"2-mark question {i+1}",
            marks=2,
            type=QuestionType.SHORT_ANSWER,
            difficulty=DifficultyLevel.EASY,
            topic_id=topic.id,
            tags_confirmed=True
        )
        db.add(q)
        questions.append(q)
    
    # Create 5-mark questions
    for i in range(12):
        q = Question(
            bank_id=question_bank.id,
            text=f"5-mark question {i+1}",
            marks=5,
            type=QuestionType.LONG_ANSWER,
            difficulty=DifficultyLevel.MEDIUM,
            topic_id=topic.id,
            tags_confirmed=True
        )
        db.add(q)
        questions.append(q)
    
    db.commit()
    return questions


@pytest.fixture
def pattern(db: Session, subject, topic):
    """Create test pattern"""
    pattern = Pattern(
        subject_id=subject.id,
        mark_distribution={"2": 0.2, "5": 0.4, "10": 0.4},
        type_distribution={"short_answer": 0.3, "long_answer": 0.7},
        topic_weights={str(topic.id): 0.8},
        difficulty_distribution={"easy": 0.2, "medium": 0.5, "hard": 0.3}
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


@pytest.fixture
def faculty(db: Session):
    """Create test faculty user"""
    user = User(
        email="faculty@test.com",
        username="faculty",
        hashed_password="hashed",
        role=UserRole.FACULTY
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestQuestionSelectorAgent:
    """Test suite for Question Selector Agent"""
    
    @pytest.mark.asyncio
    async def test_validate_constraints_valid(self, db, subject, questions):
        """Test constraint validation with valid constraints"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 60,
            "mark_distribution": {"2": 10, "5": 8}
        }
        
        result = await agent.validate_constraints(subject.id, constraints)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    
    @pytest.mark.asyncio
    async def test_validate_constraints_insufficient_questions(self, db, subject, questions):
        """Test constraint validation with insufficient questions"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 200,
            "mark_distribution": {"2": 100}
        }
        
        result = await agent.validate_constraints(subject.id, constraints)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_constraints_zero_marks(self, db, subject):
        """Test constraint validation with zero total marks"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 0,
            "mark_distribution": {}
        }
        
        result = await agent.validate_constraints(subject.id, constraints)
        
        assert result["valid"] is False
    
    @pytest.mark.asyncio
    async def test_generate_single_paper(self, db, subject, questions, pattern, faculty):
        """Test generating a single paper"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 60,
            "mark_distribution": {"2": 10, "5": 8}
        }
        
        papers = await agent.generate_papers(
            subject.id, constraints, 1, pattern, faculty.id
        )
        
        assert len(papers) == 1
        assert papers[0].total_marks == 60
    
    @pytest.mark.asyncio
    async def test_generate_multiple_papers(self, db, subject, questions, pattern, faculty):
        """Test generating multiple paper sets"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 30,
            "mark_distribution": {"2": 5, "5": 4}
        }
        
        papers = await agent.generate_papers(
            subject.id, constraints, 3, pattern, faculty.id
        )
        
        assert len(papers) == 3
        for paper in papers:
            assert paper.total_marks == 30
    
    @pytest.mark.asyncio
    async def test_question_scoring(self, db, subject, questions, pattern):
        """Test question scoring algorithm"""
        agent = QuestionSelectorAgent(db)
        
        question = questions[0]
        score = agent._score_question(question, pattern, {}, {})
        
        assert score > 0
        assert isinstance(score, float)
    
    @pytest.mark.asyncio
    async def test_diversity_score_calculation(self, db, subject, questions, pattern, faculty):
        """Test diversity score calculation"""
        agent = QuestionSelectorAgent(db)
        
        constraints = {
            "total_marks": 20,
            "mark_distribution": {"2": 10}
        }
        
        papers = await agent.generate_papers(
            subject.id, constraints, 2, pattern, faculty.id
        )
        
        diversity = agent.calculate_diversity_score(papers)
        
        assert 0 <= diversity <= 1
        assert diversity > 0  # Should have some diversity
