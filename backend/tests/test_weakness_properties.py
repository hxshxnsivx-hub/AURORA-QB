"""Property-based tests for Weakness Analyzer Agent"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session

from agents.weakness_analyzer_agent import WeaknessAnalyzerAgent
from models.question import Question, QuestionType, DifficultyLevel
from models.academic import Subject, Unit, Topic, Concept
from models.question import QuestionBank
from models.paper import Paper, PaperQuestion
from models.attempt import Attempt
from models.evaluation import Evaluation
from models.performance import TopicPerformance
from models.resource import Resource, ResourceTopicLink
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
    
    # Create resource
    resource = Resource(
        title="Test Resource",
        file_path="resource.pdf",
        resource_type="pdf"
    )
    db.add(resource)
    db.commit()
    
    # Link resource to topic
    link = ResourceTopicLink(resource_id=resource.id, topic_id=topic.id)
    db.add(link)
    db.commit()
    
    return {
        "subject": subject,
        "topic": topic,
        "concept": concept,
        "student": student,
        "faculty": faculty,
        "bank": bank,
        "resource": resource
    }


class TestWeaknessAnalyzerProperties:
    """Property-based tests for Weakness Analyzer Agent"""
    
    @pytest.mark.asyncio
    @given(
        score=st.floats(min_value=0, max_value=10),
        max_marks=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=15, deadline=5000)
    async def test_property_45_topic_performance_computation(
        self, db, setup_test_data, score, max_marks
    ):
        """
        **Validates: Requirements 10.1**
        
        Property 45: Topic Performance Computation
        
        For any evaluation, topic-wise performance scores should be computed
        as (sum of scores for topic questions) / (sum of max scores for topic questions).
        """
        agent = WeaknessAnalyzerAgent(db)
        student = setup_test_data["student"]
        subject = setup_test_data["subject"]
        topic = setup_test_data["topic"]
        bank = setup_test_data["bank"]
        faculty = setup_test_data["faculty"]
        
        # Create paper
        paper = Paper(
            subject_id=subject.id,
            faculty_id=faculty.id,
            title="Test Paper",
            total_marks=max_marks,
            constraints={}
        )
        db.add(paper)
        db.commit()
        
        # Create question
        question = Question(
            bank_id=bank.id,
            text="Test question",
            marks=max_marks,
            type=QuestionType.SHORT_ANSWER,
            difficulty=DifficultyLevel.MEDIUM,
            topic_id=topic.id,
            tags_confirmed=True
        )
        db.add(question)
        db.commit()
        
        # Add to paper
        pq = PaperQuestion(paper_id=paper.id, question_id=question.id, order=1)
        db.add(pq)
        db.commit()
        
        # Create attempt
        attempt = Attempt(
            paper_id=paper.id,
            student_id=student.id,
            status="evaluated"
        )
        db.add(attempt)
        db.commit()
        
        # Create evaluation
        evaluation = Evaluation(
            attempt_id=attempt.id,
            question_id=question.id,
            score=min(score, max_marks),  # Ensure score <= max_marks
            feedback="Test feedback",
            evaluated_by_llm=True
        )
        db.add(evaluation)
        db.commit()
        
        # Calculate performance
        performances = await agent._calculate_topic_performance(student.id, subject.id)
        
        # Verify computation
        if topic.id in performances:
            expected_percentage = min(score, max_marks) / max_marks if max_marks > 0 else 0
            actual_percentage = performances[topic.id]["percentage"]
            assert abs(actual_percentage - expected_percentage) < 0.01
    
    @pytest.mark.asyncio
    @given(percentage=st.floats(min_value=0, max_value=1))
    @settings(max_examples=20, deadline=5000)
    async def test_property_46_weakness_identification_threshold(
        self, db, setup_test_data, percentage
    ):
        """
        **Validates: Requirements 10.2**
        
        Property 46: Weakness Identification Threshold
        
        For any topic with performance score below 60%, the topic should be
        identified as a weakness.
        """
        agent = WeaknessAnalyzerAgent(db)
        student = setup_test_data["student"]
        topic = setup_test_data["topic"]
        
        # Create topic performance
        perf = TopicPerformance(
            student_id=student.id,
            topic_id=topic.id,
            total_score=percentage * 10,
            max_score=10,
            percentage=percentage,
            attempt_count=1
        )
        db.add(perf)
        db.commit()
        
        # Analyze performance
        weaknesses = await agent.analyze_performance(student.id, setup_test_data["subject"].id)
        
        # Check threshold
        weak_topic_ids = [w.topic_id for w in weaknesses]
        if percentage < 0.6:
            assert topic.id in weak_topic_ids
        else:
            assert topic.id not in weak_topic_ids
    
    @pytest.mark.asyncio
    async def test_property_48_concept_mastery_computation(
        self, db, setup_test_data
    ):
        """
        **Validates: Requirements 10.4**
        
        Property 48: Concept Mastery Computation
        
        For any student and concept, the mastery score should be computed
        from the performance scores of all topics linked to that concept.
        """
        agent = WeaknessAnalyzerAgent(db)
        student = setup_test_data["student"]
        subject = setup_test_data["subject"]
        topic = setup_test_data["topic"]
        concept = setup_test_data["concept"]
        
        # Create topic performance
        perf = TopicPerformance(
            student_id=student.id,
            topic_id=topic.id,
            total_score=7.0,
            max_score=10.0,
            percentage=0.7,
            attempt_count=1
        )
        db.add(perf)
        db.commit()
        
        # Update concept mastery
        await agent.update_concept_mastery(student.id, subject.id)
        
        # Check mastery was computed
        from models.performance import ConceptMastery
        mastery = db.query(ConceptMastery).filter(
            ConceptMastery.student_id == student.id,
            ConceptMastery.concept_id == concept.id
        ).first()
        
        assert mastery is not None
        # Mastery should be based on topic performance (0.7)
        assert abs(mastery.mastery_level - 0.7) < 0.01
    
    @pytest.mark.asyncio
    async def test_property_50_resource_recommendation_generation(
        self, db, setup_test_data
    ):
        """
        **Validates: Requirements 10.6**
        
        Property 50: Resource Recommendation Generation
        
        For any identified weakness, the system should recommend at least
        one resource linked to the weak topic.
        """
        agent = WeaknessAnalyzerAgent(db)
        topic = setup_test_data["topic"]
        
        # Get resource recommendations
        resources = await agent._recommend_resources(topic.id)
        
        # Should have at least one resource
        assert len(resources) >= 1
        assert resources[0].id == setup_test_data["resource"].id
