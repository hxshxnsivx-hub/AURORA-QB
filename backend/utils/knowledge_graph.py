"""Knowledge Graph utilities for concept relationships and queries"""

from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.academic import Concept, Topic, Unit
from models.question import Question
from models.resource import Resource, ResourceTopicLink
from models.performance import ConceptMastery
from utils.logger import logger


class KnowledgeGraph:
    """Knowledge graph query utilities"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_prerequisite_relationship(
        self,
        concept_id: UUID,
        prerequisite_id: UUID,
        strength: float = 1.0
    ) -> None:
        """Create a prerequisite relationship between concepts"""
        from models.academic import ConceptPrerequisite
        
        # Check if relationship already exists
        existing = self.db.query(ConceptPrerequisite).filter(
            ConceptPrerequisite.concept_id == concept_id,
            ConceptPrerequisite.prerequisite_id == prerequisite_id
        ).first()
        
        if existing:
            existing.strength = strength
        else:
            prereq = ConceptPrerequisite(
                concept_id=concept_id,
                prerequisite_id=prerequisite_id,
                strength=strength
            )
            self.db.add(prereq)
        
        self.db.commit()
        logger.info("Prerequisite relationship created", extra={
            "concept_id": str(concept_id),
            "prerequisite_id": str(prerequisite_id)
        })
    
    def get_questions_covering_concept(self, concept_id: UUID) -> List[Question]:
        """Get all questions that cover a specific concept"""
        
        # Get the concept's topic
        concept = self.db.query(Concept).filter(Concept.id == concept_id).first()
        if not concept:
            return []
        
        # Get all questions for this topic
        questions = self.db.query(Question).filter(
            Question.topic_id == concept.topic_id,
            Question.tags_confirmed == True
        ).all()
        
        return questions
    
    def get_concept_prerequisites(
        self,
        concept_id: UUID,
        min_strength: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get prerequisites for a concept"""
        from models.academic import ConceptPrerequisite
        
        prereqs = self.db.query(ConceptPrerequisite, Concept).join(
            Concept, ConceptPrerequisite.prerequisite_id == Concept.id
        ).filter(
            ConceptPrerequisite.concept_id == concept_id,
            ConceptPrerequisite.strength >= min_strength
        ).order_by(ConceptPrerequisite.strength.desc()).all()
        
        return [
            {
                "concept_id": str(concept.id),
                "concept_name": concept.name,
                "strength": prereq.strength
            }
            for prereq, concept in prereqs
        ]
    
    def get_weak_concepts_with_strong_prerequisites(
        self,
        student_id: UUID,
        weakness_threshold: float = 0.6,
        strength_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Find concepts where student is weak but has mastered prerequisites"""
        from models.academic import ConceptPrerequisite
        
        # Get all weak concepts for student
        weak_masteries = self.db.query(ConceptMastery).filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.mastery_level < weakness_threshold
        ).all()
        
        results = []
        
        for weak_mastery in weak_masteries:
            # Get prerequisites for this concept
            prereqs = self.db.query(ConceptPrerequisite).filter(
                ConceptPrerequisite.concept_id == weak_mastery.concept_id
            ).all()
            
            if not prereqs:
                continue
            
            # Check if prerequisites are strong
            prereq_masteries = []
            for prereq in prereqs:
                prereq_mastery = self.db.query(ConceptMastery).filter(
                    ConceptMastery.student_id == student_id,
                    ConceptMastery.concept_id == prereq.prerequisite_id
                ).first()
                
                if prereq_mastery:
                    prereq_masteries.append(prereq_mastery.mastery_level)
            
            if prereq_masteries:
                avg_prereq_mastery = sum(prereq_masteries) / len(prereq_masteries)
                
                if avg_prereq_mastery >= strength_threshold:
                    concept = self.db.query(Concept).filter(
                        Concept.id == weak_mastery.concept_id
                    ).first()
                    
                    results.append({
                        "concept_id": str(weak_mastery.concept_id),
                        "concept_name": concept.name if concept else "Unknown",
                        "mastery_level": weak_mastery.mastery_level,
                        "avg_prereq_mastery": avg_prereq_mastery,
                        "prerequisite_count": len(prereqs)
                    })
        
        return results
    
    def link_question_to_topic(self, question_id: UUID, topic_id: UUID) -> None:
        """Link a question to a topic (already done in Question model)"""
        question = self.db.query(Question).filter(Question.id == question_id).first()
        if question:
            question.topic_id = topic_id
            self.db.commit()
    
    def link_resource_to_topic(self, resource_id: UUID, topic_id: UUID) -> None:
        """Link a resource to a topic"""
        # Check if link already exists
        existing = self.db.query(ResourceTopicLink).filter(
            ResourceTopicLink.resource_id == resource_id,
            ResourceTopicLink.topic_id == topic_id
        ).first()
        
        if not existing:
            link = ResourceTopicLink(
                resource_id=resource_id,
                topic_id=topic_id
            )
            self.db.add(link)
            self.db.commit()
    
    def track_student_concept_mastery(
        self,
        student_id: UUID,
        concept_id: UUID,
        mastery_level: float
    ) -> None:
        """Track or update student's mastery of a concept"""
        mastery = self.db.query(ConceptMastery).filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id
        ).first()
        
        if mastery:
            mastery.mastery_level = mastery_level
        else:
            mastery = ConceptMastery(
                student_id=student_id,
                concept_id=concept_id,
                mastery_level=mastery_level
            )
            self.db.add(mastery)
        
        self.db.commit()
    
    def visualize_concept_graph(self, subject_id: UUID) -> Dict[str, Any]:
        """Generate visualization data for concept graph"""
        from models.academic import ConceptPrerequisite
        
        # Get all concepts for subject
        concepts = self.db.query(Concept).join(Concept.topic).join(
            Topic.unit
        ).filter(
            Topic.unit.has(subject_id=subject_id)
        ).all()
        
        # Get all prerequisite relationships
        concept_ids = [c.id for c in concepts]
        prereqs = self.db.query(ConceptPrerequisite).filter(
            ConceptPrerequisite.concept_id.in_(concept_ids)
        ).all()
        
        # Format for visualization
        nodes = [
            {
                "id": str(c.id),
                "name": c.name,
                "importance": c.importance
            }
            for c in concepts
        ]
        
        edges = [
            {
                "source": str(p.prerequisite_id),
                "target": str(p.concept_id),
                "strength": p.strength
            }
            for p in prereqs
        ]
        
        return {
            "nodes": nodes,
            "edges": edges
        }
