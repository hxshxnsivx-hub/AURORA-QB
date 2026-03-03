"""
Question Selector Agent

Selects questions for paper generation based on:
1. Constraints (marks, types, difficulty, topics)
2. Learned patterns
3. Diversity across multiple sets
4. Knowledge graph coverage
"""

from typing import Dict, Any, List, Tuple
from uuid import UUID
from collections import defaultdict
import random
from sqlalchemy.orm import Session
from sqlalchemy import and_

from agents.base import Agent
from models.question import Question, QuestionType, DifficultyLevel
from models.paper import Paper, PaperQuestion
from models.pattern import Pattern
from utils.logger import logger


class QuestionSelectorAgent(Agent):
    """Agent for selecting questions to generate exam papers"""
    
    def __init__(self, db: Session):
        super().__init__(agent_type="question_selector")
        self.db = db
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process paper generation task"""
        subject_id = UUID(task_data["subject_id"])
        constraints = task_data["constraints"]
        num_sets = task_data.get("num_sets", 1)
        faculty_id = UUID(task_data["faculty_id"])
        
        # Get pattern
        pattern = self.db.query(Pattern).filter(Pattern.subject_id == subject_id).first()
        
        # Validate constraints
        validation = await self.validate_constraints(subject_id, constraints)
        if not validation["valid"]:
            raise ValueError(f"Invalid constraints: {validation['errors']}")
        
        # Generate papers
        papers = await self.generate_papers(subject_id, constraints, num_sets, pattern, faculty_id)
        
        return {
            "papers": [{"id": str(p.id), "title": p.title} for p in papers],
            "num_sets": len(papers),
            "status": "completed"
        }
    
    async def validate_constraints(
        self,
        subject_id: UUID,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate if constraints can be satisfied"""
        errors = []
        
        # Check total marks
        total_marks = constraints.get("total_marks", 0)
        if total_marks <= 0:
            errors.append("Total marks must be positive")
        
        # Check mark distribution
        mark_dist = constraints.get("mark_distribution", {})
        if sum(mark_dist.values()) * sum(int(k) for k in mark_dist.keys()) != total_marks:
            # Allow some flexibility
            pass
        
        # Check if enough questions exist
        for marks, count in mark_dist.items():
            available = self.db.query(Question).join(Question.bank).filter(
                Question.marks == int(marks),
                Question.bank.has(subject_id=subject_id)
            ).count()
            
            if available < count:
                errors.append(f"Not enough {marks}-mark questions (need {count}, have {available})")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def generate_papers(
        self,
        subject_id: UUID,
        constraints: Dict[str, Any],
        num_sets: int,
        pattern: Pattern,
        faculty_id: UUID
    ) -> List[Paper]:
        """Generate multiple paper sets"""
        papers = []
        used_questions = set()
        
        for i in range(num_sets):
            # Select questions for this paper
            selected = await self._select_questions_for_paper(
                subject_id, constraints, pattern, used_questions
            )
            
            # Create paper
            paper = Paper(
                subject_id=subject_id,
                faculty_id=faculty_id,
                title=f"Paper Set {i+1}",
                total_marks=constraints["total_marks"],
                constraints=constraints
            )
            self.db.add(paper)
            self.db.flush()
            
            # Add questions to paper
            for order, question_id in enumerate(selected, 1):
                pq = PaperQuestion(
                    paper_id=paper.id,
                    question_id=question_id,
                    order=order
                )
                self.db.add(pq)
                used_questions.add(question_id)
            
            papers.append(paper)
        
        self.db.commit()
        return papers
    
    async def _select_questions_for_paper(
        self,
        subject_id: UUID,
        constraints: Dict[str, Any],
        pattern: Pattern,
        used_questions: set
    ) -> List[UUID]:
        """Select questions for a single paper"""
        selected = []
        mark_dist = constraints.get("mark_distribution", {})
        type_dist = constraints.get("type_distribution", {})
        difficulty_mix = constraints.get("difficulty_mix", {})
        
        for marks_str, count in mark_dist.items():
            marks = int(marks_str)
            
            # Build candidate pool
            candidates = self.db.query(Question).join(Question.bank).filter(
                and_(
                    Question.marks == marks,
                    Question.bank.has(subject_id=subject_id),
                    Question.tags_confirmed == True,
                    ~Question.id.in_(used_questions)
                )
            ).all()
            
            if len(candidates) < count:
                # Not enough questions, use what we have
                selected.extend([q.id for q in candidates])
                continue
            
            # Score candidates
            scored = []
            for q in candidates:
                score = self._score_question(q, pattern, type_dist, difficulty_mix)
                scored.append((score, q))
            
            # Sort by score and select top N
            scored.sort(reverse=True, key=lambda x: x[0])
            selected.extend([q.id for _, q in scored[:count]])
        
        return selected
    
    def _score_question(
        self,
        question: Question,
        pattern: Pattern,
        type_dist: Dict,
        difficulty_mix: Dict
    ) -> float:
        """Score a question based on pattern match and constraints"""
        score = 1.0
        
        # Pattern-based scoring
        if pattern:
            # Type match
            if question.type.value in pattern.type_distribution:
                score *= (1 + pattern.type_distribution[question.type.value])
            
            # Topic weight
            if question.topic_id and str(question.topic_id) in pattern.topic_weights:
                score *= (1 + pattern.topic_weights[str(question.topic_id)])
        
        # Constraint-based scoring
        if type_dist and question.type.value in type_dist:
            score *= 1.2
        
        if difficulty_mix and question.difficulty.value in difficulty_mix:
            score *= 1.1
        
        # Add randomness for diversity
        score *= (0.8 + random.random() * 0.4)
        
        return score
    
    def calculate_diversity_score(self, papers: List[Paper]) -> float:
        """Calculate diversity score across paper sets"""
        if len(papers) < 2:
            return 1.0
        
        # Get all question sets
        question_sets = []
        for paper in papers:
            questions = {pq.question_id for pq in paper.questions}
            question_sets.append(questions)
        
        # Calculate pairwise overlap
        overlaps = []
        for i in range(len(question_sets)):
            for j in range(i+1, len(question_sets)):
                overlap = len(question_sets[i] & question_sets[j])
                total = len(question_sets[i] | question_sets[j])
                overlaps.append(overlap / total if total > 0 else 0)
        
        # Diversity is inverse of average overlap
        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
        return 1.0 - avg_overlap
