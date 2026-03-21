"""Unit tests for Pattern Miner Agent"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from agents.pattern_miner_agent import PatternMinerAgent
from models.question import Question, QuestionBank, QuestionBankStatus, QuestionType, DifficultyLevel
from models.pattern import Pattern


class TestPatternMinerAgent:
    """Test Pattern Miner Agent functionality"""
    
    @pytest.mark.asyncio
    async def test_learn_patterns_success(self, db_session):
        """Test successful pattern learning"""
        subject_id = uuid4()
        
        # Create question bank
        bank = QuestionBank(
            subject_id=subject_id,
            faculty_id=uuid4(),
            file_path="test.pdf",
            file_name="test.pdf",
            file_size=1024,
            status=QuestionBankStatus.COMPLETED
        )
        db_session.add(bank)
        
        # Create questions with various attributes
        questions = [
            Question(bank_id=bank.id, text="Q1", marks=1, type=QuestionType.MCQ, difficulty=DifficultyLevel.EASY),
            Question(bank_id=bank.id, text="Q2", marks=2, type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.MEDIUM),
            Question(bank_id=bank.id, text="Q3", marks=5, type=QuestionType.LONG_ANSWER, difficulty=DifficultyLevel.HARD),
            Question(bank_id=bank.id, text="Q4", marks=1, type=QuestionType.MCQ, difficulty=DifficultyLevel.EASY),
        ]
        for q in questions:
            db_session.add(q)
        db_session.commit()
        
        agent = PatternMinerAgent(db_session)
        pattern = await agent.learn_patterns(subject_id)
        
        assert pattern is not None
        assert pattern.subject_id == subject_id
        assert pattern.confidence > 0
        assert len(pattern.mark_distribution) > 0
        assert len(pattern.type_distribution) > 0
    
    def test_calculate_mark_distribution(self, db_session):
        """Test mark distribution calculation"""
        agent = PatternMinerAgent(db_session)
        
        questions = [
            Mock(marks=1),
            Mock(marks=1),
            Mock(marks=2),
            Mock(marks=5),
        ]
        
        dist = agent._calculate_mark_distribution(questions)
        
        assert dist["1"] == 0.5  # 2 out of 4
        assert dist["2"] == 0.25  # 1 out of 4
        assert dist["5"] == 0.25  # 1 out of 4
        assert sum(dist.values()) == pytest.approx(1.0)
    
    def test_calculate_type_distribution(self, db_session):
        """Test type distribution calculation"""
        agent = PatternMinerAgent(db_session)
        
        questions = [
            Mock(type=Mock(value="MCQ")),
            Mock(type=Mock(value="MCQ")),
            Mock(type=Mock(value="Short Answer")),
            Mock(type=Mock(value="Long Answer")),
        ]
        
        dist = agent._calculate_type_distribution(questions)
        
        assert dist["MCQ"] == 0.5
        assert dist["Short Answer"] == 0.25
        assert dist["Long Answer"] == 0.25
        assert sum(dist.values()) == pytest.approx(1.0)
    
    def test_calculate_confidence(self, db_session):
        """Test confidence calculation based on sample size"""
        agent = PatternMinerAgent(db_session)
        
        assert agent._calculate_confidence(5) == 0.3
        assert agent._calculate_confidence(20) == 0.5
        assert agent._calculate_confidence(40) == 0.7
        assert agent._calculate_confidence(75) == 0.85
        assert agent._calculate_confidence(150) == 0.95
