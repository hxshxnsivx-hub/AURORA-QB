"""Unit tests for Grading Evaluator Agent"""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from agents.grading_evaluator_agent import GradingEvaluatorAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic
from models.question import QuestionBank
from models.answer_key import AnswerKey
from models.paper import Paper, PaperQuestion
from models.attempt import Attempt, StudentAnswer
from models.evaluation import Evaluation
from models.user import User, UserRole


@pytest.fixture
def setup_grading_data(db: Session):
    """Setup test data for grading"""
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
    
    # Create question bank
    bank = QuestionBank(
        subject_id=subject.id,
        title="Test Bank",
        file_path="test.pdf",
        status="completed"
    )
    db.add(bank)
    db.commit()
    
    # Create student and faculty
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
    
    # Create paper
    paper = Paper(
        subject_id=subject.id,
        faculty_id=faculty.id,
        title="Test Paper",
        total_marks=10,
        constraints={}
    )
    db.add(paper)
    db.commit()
    
    # Create MCQ question
    mcq_question = Question(
        bank_id=bank.id,
        text="What is 2+2?",
        marks=2,
        type=QuestionType.MCQ,
        difficulty=DifficultyLevel.EASY,
        topic_id=topic.id,
        correct_answer="4",
        tags_confirmed=True
    )
    db.add(mcq_question)
    db.commit()
    
    # Create answer key
    answer_key = AnswerKey(
        question_id=mcq_question.id,
        model_answer="4",
        rubric={"criteria": [{"description": "Correct answer", "points": 2}]},
        resource_citations=[],
        reviewed_by_faculty=True
    )
    db.add(answer_key)
    db.commit()
    
    # Add question to paper
    pq = PaperQuestion(
        paper_id=paper.id,
        question_id=mcq_question.id,
        order=1
    )
    db.add(pq)
    db.commit()
    
    # Create attempt
    attempt = Attempt(
        paper_id=paper.id,
        student_id=student.id,
        status="submitted"
    )
    db.add(attempt)
    db.commit()
    
    return {
        "subject": subject,
        "topic": topic,
        "bank": bank,
        "student": student,
        "faculty": faculty,
        "paper": paper,
        "mcq_question": mcq_question,
        "answer_key": answer_key,
        "attempt": attempt
    }


class TestGradingEvaluatorAgent:
    """Test suite for Grading Evaluator Agent"""
    
    @pytest.mark.asyncio
    async def test_grade_mcq_correct(self, db, setup_grading_data):
        """Test grading correct MCQ answer"""
        agent = GradingEvaluatorAgent(db)
        
        # Create student answer
        student_answer = StudentAnswer(
            attempt_id=setup_grading_data["attempt"].id,
            question_id=setup_grading_data["mcq_question"].id,
            answer_text="4"
        )
        db.add(student_answer)
        db.commit()
        db.refresh(student_answer)
        
        score, feedback = await agent.evaluate_answer(student_answer)
        
        assert score == 2.0
        assert "correct" in feedback.lower()
    
    @pytest.mark.asyncio
    async def test_grade_mcq_incorrect(self, db, setup_grading_data):
        """Test grading incorrect MCQ answer"""
        agent = GradingEvaluatorAgent(db)
        
        # Create student answer
        student_answer = StudentAnswer(
            attempt_id=setup_grading_data["attempt"].id,
            question_id=setup_grading_data["mcq_question"].id,
            answer_text="5"
        )
        db.add(student_answer)
        db.commit()
        db.refresh(student_answer)
        
        score, feedback = await agent.evaluate_answer(student_answer)
        
        assert score == 0.0
        assert "incorrect" in feedback.lower()
    
    @pytest.mark.asyncio
    async def test_calculate_total_score(self, db, setup_grading_data):
        """Test total score calculation"""
        agent = GradingEvaluatorAgent(db)
        attempt_id = setup_grading_data["attempt"].id
        
        # Create evaluations
        eval1 = Evaluation(
            attempt_id=attempt_id,
            question_id=setup_grading_data["mcq_question"].id,
            score=2.0,
            feedback="Good",
            evaluated_by_llm=False
        )
        db.add(eval1)
        db.commit()
        
        total = agent.calculate_total_score(attempt_id)
        
        assert total == 2.0
    
    @pytest.mark.asyncio
    async def test_generate_feedback_summary(self, db, setup_grading_data):
        """Test feedback summary generation"""
        agent = GradingEvaluatorAgent(db)
        attempt_id = setup_grading_data["attempt"].id
        
        # Create evaluation
        eval1 = Evaluation(
            attempt_id=attempt_id,
            question_id=setup_grading_data["mcq_question"].id,
            score=2.0,
            feedback="Good",
            evaluated_by_llm=False
        )
        db.add(eval1)
        db.commit()
        
        summary = agent.generate_feedback_summary(attempt_id)
        
        assert "Total Score" in summary
        assert "2" in summary
