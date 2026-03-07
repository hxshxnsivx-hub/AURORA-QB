"""Unit tests for Answer Key Generator Agent"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from agents.answer_key_generator_agent import AnswerKeyGeneratorAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic
from models.question import QuestionBank
from models.answer_key import AnswerKey
from models.resource import Resource, ResourceTopicLink


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
def mcq_question(db: Session, question_bank, topic):
    """Create MCQ question"""
    q = Question(
        bank_id=question_bank.id,
        text="What is 2+2?",
        marks=2,
        type=QuestionType.MCQ,
        difficulty=DifficultyLevel.EASY,
        topic_id=topic.id,
        correct_answer="4",
        tags_confirmed=True
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@pytest.fixture
def short_answer_question(db: Session, question_bank, topic):
    """Create short answer question"""
    q = Question(
        bank_id=question_bank.id,
        text="Explain the concept of linear equations.",
        marks=5,
        type=QuestionType.SHORT_ANSWER,
        difficulty=DifficultyLevel.MEDIUM,
        topic_id=topic.id,
        tags_confirmed=True
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@pytest.fixture
def resource(db: Session, topic):
    """Create test resource"""
    resource = Resource(
        title="Linear Equations Guide",
        file_path="guide.pdf",
        resource_type="pdf"
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    
    # Link to topic
    link = ResourceTopicLink(resource_id=resource.id, topic_id=topic.id)
    db.add(link)
    db.commit()
    
    return resource


class TestAnswerKeyGeneratorAgent:
    """Test suite for Answer Key Generator Agent"""
    
    @pytest.mark.asyncio
    async def test_generate_answer_key_mcq(self, db, mcq_question):
        """Test answer key generation for MCQ"""
        agent = AnswerKeyGeneratorAgent(db)
        
        answer_key = await agent.generate_answer_key(mcq_question.id)
        
        assert answer_key is not None
        assert answer_key.question_id == mcq_question.id
        assert answer_key.model_answer == "4"
        assert "criteria" in answer_key.rubric
        assert len(answer_key.rubric["criteria"]) > 0
    
    @pytest.mark.asyncio
    async def test_generate_answer_key_short_answer(self, db, short_answer_question):
        """Test answer key generation for short answer"""
        agent = AnswerKeyGeneratorAgent(db)
        
        answer_key = await agent.generate_answer_key(short_answer_question.id)
        
        assert answer_key is not None
        assert answer_key.question_id == short_answer_question.id
        assert len(answer_key.model_answer) > 0
        assert "criteria" in answer_key.rubric
    
    @pytest.mark.asyncio
    async def test_answer_key_not_duplicated(self, db, mcq_question):
        """Test that answer key is not duplicated"""
        agent = AnswerKeyGeneratorAgent(db)
        
        # Generate first time
        answer_key1 = await agent.generate_answer_key(mcq_question.id)
        
        # Generate second time
        answer_key2 = await agent.generate_answer_key(mcq_question.id)
        
        # Should return same answer key
        assert answer_key1.id == answer_key2.id
    
    @pytest.mark.asyncio
    async def test_simple_rubric_creation(self, db, mcq_question):
        """Test simple rubric creation for MCQ"""
        agent = AnswerKeyGeneratorAgent(db)
        
        rubric = agent._create_simple_rubric(mcq_question.marks)
        
        assert "criteria" in rubric
        assert len(rubric["criteria"]) == 1
        assert rubric["criteria"][0]["points"] == mcq_question.marks
    
    @pytest.mark.asyncio
    async def test_get_relevant_resources(self, db, short_answer_question, resource):
        """Test retrieving relevant resources"""
        agent = AnswerKeyGeneratorAgent(db)
        
        resources = await agent._get_relevant_resources(short_answer_question)
        
        assert len(resources) > 0
        assert resources[0].id == resource.id
    
    @pytest.mark.asyncio
    async def test_answer_key_reviewed_flag(self, db, mcq_question):
        """Test that answer key starts as not reviewed"""
        agent = AnswerKeyGeneratorAgent(db)
        
        answer_key = await agent.generate_answer_key(mcq_question.id)
        
        assert answer_key.reviewed_by_faculty is False
