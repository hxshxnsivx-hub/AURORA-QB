"""Weakness Analyzer Agent - Analyzes student performance to identify weaknesses"""

from typing import Dict, Any, List
from uuid import UUID
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from agents.base import Agent
from models.evaluation import Evaluation
from models.attempt import Attempt
from models.question import Question
from models.academic import Topic, Concept
from models.performance import TopicPerformance, Weakness, ConceptMastery
from models.resource import Resource, ResourceTopicLink
from utils.logger import logger


class WeaknessAnalyzerAgent(Agent):
    """Analyzes student performance to identify weaknesses and recommend resources"""
    
    def __init__(self, db: Session):
        super().__init__(agent_type="weakness_analyzer")
        self.db = db
        self.weakness_threshold = 0.6  # 60% threshold
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance for a student after evaluation"""
        student_id = UUID(task_data["student_id"])
        evaluation_id = UUID(task_data.get("evaluation_id"))
        
        # Get the attempt
        evaluation = self.db.query(Evaluation).filter(
            Evaluation.id == evaluation_id
        ).first()
        
        if not evaluation:
            raise ValueError(f"Evaluation {evaluation_id} not found")
        
        attempt = evaluation.attempt
        subject_id = attempt.paper.subject_id
        
        # Analyze performance
        weaknesses = await self.analyze_performance(student_id, subject_id)
        
        # Update concept mastery
        await self.update_concept_mastery(student_id, subject_id)
        
        return {
            "student_id": str(student_id),
            "subject_id": str(subject_id),
            "weaknesses_count": len(weaknesses),
            "weaknesses": [
                {
                    "topic_id": str(w.topic_id),
                    "severity": w.severity,
                    "mastery_score": w.mastery_score
                }
                for w in weaknesses
            ]
        }
    
    async def analyze_performance(
        self,
        student_id: UUID,
        subject_id: UUID
    ) -> List[Weakness]:
        """Analyze student performance and identify weaknesses"""
        
        # Calculate topic-wise performance
        topic_performances = await self._calculate_topic_performance(
            student_id, subject_id
        )
        
        # Identify weaknesses
        weaknesses = []
        for topic_id, performance in topic_performances.items():
            if performance["percentage"] < self.weakness_threshold:
                # Get or create weakness
                weakness = self.db.query(Weakness).filter(
                    Weakness.student_id == student_id,
                    Weakness.topic_id == topic_id
                ).first()
                
                if not weakness:
                    weakness = Weakness(
                        student_id=student_id,
                        topic_id=topic_id
                    )
                    self.db.add(weakness)
                
                # Calculate severity
                severity = self._calculate_severity(performance["percentage"])
                weakness.severity = severity
                weakness.mastery_score = performance["percentage"]
                
                # Get recommended resources
                resources = await self._recommend_resources(topic_id)
                weakness.recommended_resources = [str(r.id) for r in resources]
                
                weaknesses.append(weakness)
        
        self.db.commit()
        return weaknesses
    
    async def _calculate_topic_performance(
        self,
        student_id: UUID,
        subject_id: UUID
    ) -> Dict[UUID, Dict]:
        """Calculate topic-wise performance scores"""
        
        # Get all attempts for this student and subject
        attempts = self.db.query(Attempt).join(Attempt.paper).filter(
            Attempt.student_id == student_id,
            Attempt.paper.has(subject_id=subject_id),
            Attempt.status == "evaluated"
        ).all()
        
        topic_scores = defaultdict(lambda: {"total": 0.0, "max": 0.0, "count": 0})
        
        for attempt in attempts:
            # Get evaluations for this attempt
            evaluations = self.db.query(Evaluation).filter(
                Evaluation.attempt_id == attempt.id
            ).all()
            
            for evaluation in evaluations:
                question = evaluation.question
                if question.topic_id:
                    topic_scores[question.topic_id]["total"] += evaluation.score
                    topic_scores[question.topic_id]["max"] += question.marks
                    topic_scores[question.topic_id]["count"] += 1
        
        # Calculate percentages
        topic_performances = {}
        for topic_id, scores in topic_scores.items():
            percentage = (scores["total"] / scores["max"]) if scores["max"] > 0 else 0
            
            # Update or create TopicPerformance
            perf = self.db.query(TopicPerformance).filter(
                TopicPerformance.student_id == student_id,
                TopicPerformance.topic_id == topic_id
            ).first()
            
            if not perf:
                perf = TopicPerformance(
                    student_id=student_id,
                    topic_id=topic_id
                )
                self.db.add(perf)
            
            perf.total_score = scores["total"]
            perf.max_score = scores["max"]
            perf.percentage = percentage
            perf.attempt_count = scores["count"]
            
            topic_performances[topic_id] = {
                "total": scores["total"],
                "max": scores["max"],
                "percentage": percentage,
                "count": scores["count"]
            }
        
        self.db.commit()
        return topic_performances
    
    def _calculate_severity(self, percentage: float) -> float:
        """Calculate weakness severity (0-1 scale)"""
        # Severity increases as percentage decreases below threshold
        if percentage >= self.weakness_threshold:
            return 0.0
        
        # Linear scale: 0% = severity 1.0, 60% = severity 0.0
        severity = (self.weakness_threshold - percentage) / self.weakness_threshold
        return min(max(severity, 0.0), 1.0)
    
    async def _recommend_resources(self, topic_id: UUID) -> List[Resource]:
        """Recommend resources for a weak topic"""
        
        # Get resources linked to this topic
        resource_links = self.db.query(ResourceTopicLink).filter(
            ResourceTopicLink.topic_id == topic_id
        ).limit(5).all()
        
        resources = []
        for link in resource_links:
            resource = self.db.query(Resource).filter(
                Resource.id == link.resource_id
            ).first()
            if resource:
                resources.append(resource)
        
        return resources
    
    async def update_concept_mastery(
        self,
        student_id: UUID,
        subject_id: UUID
    ) -> None:
        """Update concept mastery based on topic performance"""
        
        # Get topic performances
        topic_perfs = self.db.query(TopicPerformance).filter(
            TopicPerformance.student_id == student_id
        ).all()
        
        # Map topics to concepts
        concept_scores = defaultdict(lambda: {"total": 0.0, "count": 0})
        
        for perf in topic_perfs:
            # Get concepts for this topic
            concepts = self.db.query(Concept).filter(
                Concept.topic_id == perf.topic_id
            ).all()
            
            for concept in concepts:
                concept_scores[concept.id]["total"] += perf.percentage
                concept_scores[concept.id]["count"] += 1
        
        # Update concept mastery
        for concept_id, scores in concept_scores.items():
            mastery_level = scores["total"] / scores["count"] if scores["count"] > 0 else 0
            
            mastery = self.db.query(ConceptMastery).filter(
                ConceptMastery.student_id == student_id,
                ConceptMastery.concept_id == concept_id
            ).first()
            
            if not mastery:
                mastery = ConceptMastery(
                    student_id=student_id,
                    concept_id=concept_id
                )
                self.db.add(mastery)
            
            mastery.mastery_level = mastery_level
        
        self.db.commit()
    
    def identify_weaknesses(
        self,
        student_id: UUID,
        subject_id: UUID
    ) -> List[Weakness]:
        """Get all weaknesses for a student in a subject"""
        
        weaknesses = self.db.query(Weakness).join(Weakness.topic).join(
            Topic.unit
        ).filter(
            Weakness.student_id == student_id,
            Topic.unit.has(subject_id=subject_id)
        ).order_by(Weakness.severity.desc()).all()
        
        return weaknesses
