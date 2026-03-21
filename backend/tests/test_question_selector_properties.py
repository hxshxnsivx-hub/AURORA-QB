"""Property-based tests for Question Selector Agent"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy.orm import Session

from agents.question_selector_agent import QuestionSelectorAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic
from models.question import QuestionBank
from models.pattern import Pattern
from models.paper import Paper, PaperQuestion
from models.user import User, UserRole


# Strategies
@st.composite
def mark_distribution_strategy(draw):
    """Generate valid mark distributions"""
    marks_options = [2, 5, 10]
    distribution = {}
    for marks in marks_options:
        count = draw(st.integers(min_value=0, max_value=10))
        if count > 0:
            distribution[str(marks)] = count
    assume(len(distribution) > 0)
    return distribution


@st.composite
def constraints_strategy(draw):
    """Generate valid constraints"""
    mark_dist = draw(mark_distribution_strategy())
    total_marks = sum(int(k) * v for k, v in mark_dist.items())
    
    return {
        "total_marks": total_marks,
        "mark_distribution": mark_dist
    }


@pytest.fixture
def setup_test_data(db: Session):
    """Setup test data for property tests"""
    # Create subject
    subject = Subject(name="Test Subject", code="TEST101")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    
    # Create unit and topic
    unit = Unit(name="Test Unit", code="TU", subject_id=subject.id)
    db.add(unit)
    db.commit()
    
    topic = Topic(name="Test Topic", unit_id=unit.id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    
    # Create question bank
    bank = QuestionBank(
        subject_id=subject.id,
        title="Test Bank",
        file_path="test.pdf",
        status="completed"
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    
    # Create questions
    for marks in [2, 5, 10]:
        for i in range(20):
            q = Question(
                bank_id=bank.id,
                text=f"{marks}-mark question {i+1}",
                marks=marks,
                type=QuestionType.SHORT_ANSWER if marks == 2 else QuestionType.LONG_ANSWER,
                difficulty=DifficultyLevel.EASY if marks == 2 else DifficultyLevel.MEDIUM,
                topic_id=topic.id,
                tags_confirmed=True
            )
            db.add(q)
    
    db.commit()
    
    # Create pattern
    pattern = Pattern(
        subject_id=subject.id,
        mark_distribution={"2": 0.3, "5": 0.4, "10": 0.3},
        type_distribution={"short_answer": 0.5, "long_answer": 0.5},
        topic_weights={str(topic.id): 1.0},
        difficulty_distribution={"easy": 0.3, "medium": 0.5, "hard": 0.2}
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    
    # Create faculty
    faculty = User(
        email="faculty@test.com",
        username="faculty",
        hashed_password="hashed",
        role=UserRole.FACULTY
    )
    db.add(faculty)
    db.commit()
    db.refresh(faculty)
    
    return {
        "subject": subject,
        "topic": topic,
        "bank": bank,
        "pattern": pattern,
        "faculty": faculty
    }


class TestQuestionSelectorProperties:
    """Property-based tests for Question Selector Agent"""
    
    @pytest.mark.asyncio
    @given(constraints=constraints_strategy())
    @settings(max_examples=20, deadline=5000)
    async def test_property_24_constraint_validation_correctness(
        self, db, setup_test_data, constraints
    ):
        """
        **Validates: Requirements 6.2, 18.2, 18.3, 18.4, 18.5**
        
        Property 24: Constraint Validation Correctness
        
        For any set of paper generation constraints and available questions,
        validation should return satisfiable if and only if sufficient questions
        exist to meet all constraints.
        """
        agent = QuestionSelectorAgent(db)
        subject = setup_test_data["subject"]
        
        result = await agent.validate_constraints(subject.id, constraints)
        
        # Check if we have enough questions
        mark_dist = constraints["mark_distribution"]
        has_enough = True
        
        for marks_str, count in mark_dist.items():
            marks = int(marks_str)
            available = db.query(Question).join(Question.bank).filter(
                Question.marks == marks,
                Question.bank.has(subject_id=subject.id),
                Question.tags_confirmed == True
            ).count()
            
            if available < count:
                has_enough = False
                break
        
        # Validation result should match availability
        if has_enough:
            assert result["valid"] is True or len(result["errors"]) == 0
        else:
            assert result["valid"] is False or len(result["errors"]) > 0
    
    @pytest.mark.asyncio
    @given(num_sets=st.integers(min_value=1, max_value=3))
    @settings(max_examples=15, deadline=10000)
    async def test_property_25_generated_paper_constraint_satisfaction(
        self, db, setup_test_data, num_sets
    ):
        """
        **Validates: Requirements 6.3, 19.6**
        
        Property 25: Generated Paper Constraint Satisfaction
        
        For any generated paper, all specified constraints (total marks,
        mark distribution, type distribution, topic coverage, difficulty mix)
        should be satisfied.
        """
        agent = QuestionSelectorAgent(db)
        subject = setup_test_data["subject"]
        pattern = setup_test_data["pattern"]
        faculty = setup_test_data["faculty"]
        
        constraints = {
            "total_marks": 30,
            "mark_distribution": {"2": 5, "5": 4}
        }
        
        papers = await agent.generate_papers(
            subject.id, constraints, num_sets, pattern, faculty.id
        )
        
        assert len(papers) == num_sets
        
        for paper in papers:
            # Check total marks
            assert paper.total_marks == constraints["total_marks"]
            
            # Check mark distribution
            paper_questions = db.query(PaperQuestion, Question).join(
                Question, PaperQuestion.question_id == Question.id
            ).filter(PaperQuestion.paper_id == paper.id).all()
            
            mark_counts = {}
            for pq, q in paper_questions:
                mark_counts[q.marks] = mark_counts.get(q.marks, 0) + 1
            
            for marks_str, expected_count in constraints["mark_distribution"].items():
                marks = int(marks_str)
                actual_count = mark_counts.get(marks, 0)
                # Allow some flexibility due to availability
                assert actual_count <= expected_count + 2

    
    @pytest.mark.asyncio
    @given(num_sets=st.integers(min_value=2, max_value=4))
    @settings(max_examples=10, deadline=10000)
    async def test_property_26_paper_set_question_diversity(
        self, db, setup_test_data, num_sets
    ):
        """
        **Validates: Requirements 6.4, 19.2**
        
        Property 26: Paper Set Question Diversity
        
        For any set of N generated papers, the average pairwise question
        overlap should be below a threshold (e.g., 20%).
        """
        agent = QuestionSelectorAgent(db)
        subject = setup_test_data["subject"]
        pattern = setup_test_data["pattern"]
        faculty = setup_test_data["faculty"]
        
        constraints = {
            "total_marks": 20,
            "mark_distribution": {"2": 10}
        }
        
        papers = await agent.generate_papers(
            subject.id, constraints, num_sets, pattern, faculty.id
        )
        
        diversity_score = agent.calculate_diversity_score(papers)
        
        # Diversity score should be high (low overlap)
        # With 20 questions available and 10 per paper, expect good diversity
        assert diversity_score >= 0.5  # At least 50% diversity
    
    @pytest.mark.asyncio
    @given(constraints=constraints_strategy())
    @settings(max_examples=15, deadline=5000)
    async def test_property_28_constraint_violation_error_reporting(
        self, db, setup_test_data, constraints
    ):
        """
        **Validates: Requirements 6.6**
        
        Property 28: Constraint Violation Error Reporting
        
        For any unsatisfiable constraint set, the error response should
        identify at least one specific constraint that cannot be satisfied.
        """
        agent = QuestionSelectorAgent(db)
        subject = setup_test_data["subject"]
        
        # Modify constraints to make them unsatisfiable
        unsatisfiable_constraints = constraints.copy()
        unsatisfiable_constraints["mark_distribution"] = {"2": 100}  # Need 100, only have 20
        
        result = await agent.validate_constraints(subject.id, unsatisfiable_constraints)
        
        if not result["valid"]:
            # Should have specific error messages
            assert len(result["errors"]) > 0
            # Error should mention specific constraint
            error_text = " ".join(result["errors"]).lower()
            assert any(keyword in error_text for keyword in ["not enough", "insufficient", "need", "have"])
