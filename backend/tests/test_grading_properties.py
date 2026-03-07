"""Property-based tests for Grading Evaluator Agent"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session

from agents.grading_evaluator_agent import GradingEvaluatorAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic
from models.question import QuestionBank
from models.answer_key import AnswerKey
from models.paper import Paper
from models.attempt import Attempt, StudentAnswer
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
    
    # Create question bank
    bank = QuestionBank(
        subject_id=subject.id,
        title="Test Bank",
        file_path="test.pdf",
        status="completed"
    )
    db.add(bank)
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
    
    # Create paper
    paper = Paper(
        subject_id=subject.id,
        faculty_id=faculty.id,
        title="Test Paper",
        total_marks=100,
        constraints={}
    )
    db.add(paper)
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
        "attempt": attempt
    }


class TestGradingEvaluatorProperties:
    """Property-based tests for Grading Evaluator Agent"""
    
    @pytest.mark.asyncio
    @given(
        correct_answer=st.text(min_size=1, max_size=20),
        student_answer=st.text(min_size=1, max_size=20)
    )
    @settings(max_examples=20, deadline=5000)
    async def test_property_39_mcq_grading_determinism(
        self, db, setup_test_data, correct_answer, student_answer
    ):
        """
        **Validates: Requirements 9.1**
        
        Property 39: MCQ Grading Determinism
        
        For any MCQ or True/False answer, grading should assign full marks
        if the answer exactly matches the correct answer, and zero marks otherwise.
        """
        agent = GradingEvaluatorAgent(db)
        bank = setup_test_data["bank"]
        topic = setup_test_data["topic"]
        attempt = setup_test_data["attempt"]
        
        # Create MCQ question
        question = Question(
            bank_id=bank.id,
            text="Test question",
            marks=5,
            type=QuestionType.MCQ,
            difficulty=DifficultyLevel.EASY,
            topic_id=topic.id,
            correct_answer=correct_answer,
            tags_confirmed=True
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        
        # Create answer key
        answer_key = AnswerKey(
            question_id=question.id,
            model_answer=correct_answer,
            rubric={"criteria": [{"description": "Correct", "points": 5}]},
            resource_citations=[],
            reviewed_by_faculty=True
        )
        db.add(answer_key)
        db.commit()
        
        # Create student answer
        student_ans = StudentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=student_answer
        )
        db.add(student_ans)
        db.commit()
        db.refresh(student_ans)
        
        # Evaluate
        score, feedback = await agent.evaluate_answer(student_ans)
        
        # Check determinism
        if student_answer.strip().lower() == correct_answer.strip().lower():
            assert score == 5.0
        else:
            assert score == 0.0
    
    @pytest.mark.asyncio
    @given(marks=st.integers(min_value=1, max_value=20))
    @settings(max_examples=15, deadline=10000)
    async def test_property_42_score_bounds_enforcement(
        self, db, setup_test_data, marks
    ):
        """
        **Validates: Requirements 9.4**
        
        Property 42: Score Bounds Enforcement
        
        For any question evaluation, the awarded score should be between 0
        and the question's maximum marks (inclusive).
        """
        agent = GradingEvaluatorAgent(db)
        bank = setup_test_data["bank"]
        topic = setup_test_data["topic"]
        attempt = setup_test_data["attempt"]
        
        # Create question
        question = Question(
            bank_id=bank.id,
            text="Test question",
            marks=marks,
            type=QuestionType.MCQ,
            difficulty=DifficultyLevel.MEDIUM,
            topic_id=topic.id,
            correct_answer="Answer",
            tags_confirmed=True
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        
        # Create answer key
        answer_key = AnswerKey(
            question_id=question.id,
            model_answer="Answer",
            rubric={"criteria": [{"description": "Correct", "points": marks}]},
            resource_citations=[],
            reviewed_by_faculty=True
        )
        db.add(answer_key)
        db.commit()
        
        # Create student answer
        student_ans = StudentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text="Some answer"
        )
        db.add(student_ans)
        db.commit()
        db.refresh(student_ans)
        
        # Evaluate
        score, feedback = await agent.evaluate_answer(student_ans)
        
        # Check bounds
        assert 0 <= score <= marks
    
    @pytest.mark.asyncio
    @given(answer_text=st.text(min_size=0, max_size=100))
    @settings(max_examples=15, deadline=5000)
    async def test_property_43_feedback_generation(
        self, db, setup_test_data, answer_text
    ):
        """
        **Validates: Requirements 9.5**
        
        Property 43: Feedback Generation
        
        For any evaluated question, the evaluation should include
        non-empty feedback text.
        """
        agent = GradingEvaluatorAgent(db)
        bank = setup_test_data["bank"]
        topic = setup_test_data["topic"]
        attempt = setup_test_data["attempt"]
        
        # Create question
        question = Question(
            bank_id=bank.id,
            text="Test question",
            marks=5,
            type=QuestionType.MCQ,
            difficulty=DifficultyLevel.EASY,
            topic_id=topic.id,
            correct_answer="Correct",
            tags_confirmed=True
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        
        # Create answer key
        answer_key = AnswerKey(
            question_id=question.id,
            model_answer="Correct",
            rubric={"criteria": [{"description": "Correct", "points": 5}]},
            resource_citations=[],
            reviewed_by_faculty=True
        )
        db.add(answer_key)
        db.commit()
        
        # Create student answer
        student_ans = StudentAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=answer_text
        )
        db.add(student_ans)
        db.commit()
        db.refresh(student_ans)
        
        # Evaluate
        score, feedback = await agent.evaluate_answer(student_ans)
        
        # Check feedback exists
        assert feedback is not None
        assert len(feedback) > 0
        assert isinstance(feedback, str)
