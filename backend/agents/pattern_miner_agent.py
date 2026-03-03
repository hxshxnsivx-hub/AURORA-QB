"""
Pattern Miner Agent

This agent analyzes question banks to learn exam patterns including:
1. Mark distribution
2. Type distribution
3. Topic weights
4. Difficulty distribution by marks
"""

from typing import Dict, Any, List
from uuid import UUID
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from sqlalchemy import func

from agents.base import Agent
from models.question import Question, QuestionBank, QuestionBankStatus
from models.pattern import Pattern
from utils.logger import logger


class PatternMinerAgent(Agent):
    """
    Agent responsible for learning exam patterns from question banks.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the Pattern Miner Agent.
        
        Args:
            db: Database session
        """
        super().__init__(agent_type="pattern_miner")
        self.db = db
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process pattern learning task.
        
        Args:
            task_data: Contains subject_id and optionally bank_ids
        
        Returns:
            Result with pattern statistics
        """
        subject_id = task_data.get("subject_id")
        bank_ids = task_data.get("bank_ids")  # Optional: specific banks to analyze
        
        if not subject_id:
            raise ValueError("subject_id is required")
        
        try:
            # Learn patterns from question banks
            pattern = await self.learn_patterns(subject_id, bank_ids)
            
            logger.info(f"Pattern learned successfully", extra={
                "subject_id": str(subject_id),
                "pattern_id": str(pattern.id),
                "confidence": pattern.confidence
            })
            
            return {
                "pattern_id": str(pattern.id),
                "subject_id": str(subject_id),
                "confidence": pattern.confidence,
                "mark_distribution": pattern.mark_distribution,
                "type_distribution": pattern.type_distribution,
                "topic_count": len(pattern.topic_weights),
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Pattern learning failed", extra={
                "subject_id": str(subject_id),
                "error": str(e)
            })
            raise
    
    async def learn_patterns(
        self,
        subject_id: UUID,
        bank_ids: List[UUID] = None
    ) -> Pattern:
        """
        Learn patterns from question banks for a subject.
        
        Args:
            subject_id: Subject to learn patterns for
            bank_ids: Optional list of specific banks to analyze
        
        Returns:
            Pattern object with learned distributions
        """
        # Query questions from completed banks
        query = self.db.query(Question).join(QuestionBank).filter(
            QuestionBank.subject_id == subject_id,
            QuestionBank.status == QuestionBankStatus.COMPLETED
        )
        
        if bank_ids:
            query = query.filter(QuestionBank.id.in_(bank_ids))
        
        questions = query.all()
        
        if not questions:
            raise ValueError(f"No questions found for subject {subject_id}")
        
        # Calculate distributions
        mark_dist = self._calculate_mark_distribution(questions)
        type_dist = self._calculate_type_distribution(questions)
        topic_weights = self._calculate_topic_weights(questions)
        difficulty_by_marks = self._calculate_difficulty_by_marks(questions)
        
        # Calculate confidence based on sample size
        confidence = self._calculate_confidence(len(questions))
        
        # Check if pattern already exists for this subject
        existing_pattern = self.db.query(Pattern).filter(
            Pattern.subject_id == subject_id
        ).first()
        
        if existing_pattern:
            # Update existing pattern
            existing_pattern.mark_distribution = mark_dist
            existing_pattern.type_distribution = type_dist
            existing_pattern.topic_weights = topic_weights
            existing_pattern.difficulty_by_marks = difficulty_by_marks
            existing_pattern.confidence = confidence
            pattern = existing_pattern
        else:
            # Create new pattern
            pattern = Pattern(
                subject_id=subject_id,
                mark_distribution=mark_dist,
                type_distribution=type_dist,
                topic_weights=topic_weights,
                difficulty_by_marks=difficulty_by_marks,
                confidence=confidence
            )
            self.db.add(pattern)
        
        self.db.commit()
        self.db.refresh(pattern)
        
        return pattern
    
    def _calculate_mark_distribution(self, questions: List[Question]) -> Dict[str, float]:
        """
        Calculate mark distribution as frequencies.
        
        Args:
            questions: List of questions
        
        Returns:
            Dictionary mapping marks to frequency (0-1)
        """
        mark_counts = Counter(q.marks for q in questions)
        total = len(questions)
        
        # Convert to frequencies
        distribution = {
            str(marks): count / total
            for marks, count in mark_counts.items()
        }
        
        return distribution
    
    def _calculate_type_distribution(self, questions: List[Question]) -> Dict[str, float]:
        """
        Calculate type distribution as percentages.
        
        Args:
            questions: List of questions
        
        Returns:
            Dictionary mapping type to percentage (0-1)
        """
        type_counts = Counter(q.type.value for q in questions)
        total = len(questions)
        
        # Convert to percentages
        distribution = {
            qtype: count / total
            for qtype, count in type_counts.items()
        }
        
        return distribution
    
    def _calculate_topic_weights(self, questions: List[Question]) -> Dict[str, float]:
        """
        Calculate topic weights based on frequency.
        
        Args:
            questions: List of questions
        
        Returns:
            Dictionary mapping topic_id to weight (0-1)
        """
        # Count questions per topic (only for questions with confirmed topics)
        topic_counts = Counter(
            str(q.topic_id) for q in questions
            if q.topic_id is not None
        )
        
        if not topic_counts:
            return {}
        
        total = sum(topic_counts.values())
        
        # Convert to weights
        weights = {
            topic_id: count / total
            for topic_id, count in topic_counts.items()
        }
        
        return weights
    
    def _calculate_difficulty_by_marks(
        self,
        questions: List[Question]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate difficulty distribution for each mark category.
        
        Args:
            questions: List of questions
        
        Returns:
            Nested dictionary: {marks: {difficulty: percentage}}
        """
        # Group questions by marks
        by_marks = defaultdict(list)
        for q in questions:
            by_marks[q.marks].append(q)
        
        # Calculate difficulty distribution for each mark category
        result = {}
        for marks, mark_questions in by_marks.items():
            difficulty_counts = Counter(q.difficulty.value for q in mark_questions)
            total = len(mark_questions)
            
            result[str(marks)] = {
                difficulty: count / total
                for difficulty, count in difficulty_counts.items()
            }
        
        return result
    
    def _calculate_confidence(self, sample_size: int) -> float:
        """
        Calculate confidence score based on sample size.
        
        Args:
            sample_size: Number of questions analyzed
        
        Returns:
            Confidence score (0-1)
        """
        # Confidence increases with sample size, plateaus at 100 questions
        # Using logarithmic scale
        if sample_size < 10:
            return 0.3
        elif sample_size < 30:
            return 0.5
        elif sample_size < 50:
            return 0.7
        elif sample_size < 100:
            return 0.85
        else:
            return 0.95
    
    async def aggregate_patterns(
        self,
        subject_id: UUID,
        new_bank_id: UUID
    ) -> Pattern:
        """
        Update pattern by aggregating with a new question bank.
        
        Args:
            subject_id: Subject ID
            new_bank_id: New bank to include in pattern
        
        Returns:
            Updated pattern
        """
        # Get existing pattern
        pattern = self.db.query(Pattern).filter(
            Pattern.subject_id == subject_id
        ).first()
        
        if not pattern:
            # No existing pattern, learn from scratch
            return await self.learn_patterns(subject_id, [new_bank_id])
        
        # Re-learn patterns including all banks
        return await self.learn_patterns(subject_id)
    
    def get_pattern_visualization_data(self, pattern: Pattern) -> Dict[str, Any]:
        """
        Generate visualization data for a pattern.
        
        Args:
            pattern: Pattern object
        
        Returns:
            Dictionary with chart-ready data
        """
        return {
            "mark_distribution": {
                "labels": list(pattern.mark_distribution.keys()),
                "values": list(pattern.mark_distribution.values())
            },
            "type_distribution": {
                "labels": list(pattern.type_distribution.keys()),
                "values": list(pattern.type_distribution.values())
            },
            "difficulty_by_marks": pattern.difficulty_by_marks,
            "confidence": pattern.confidence,
            "topic_count": len(pattern.topic_weights)
        }
