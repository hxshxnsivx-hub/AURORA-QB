"""Roadmap Agent - Interfaces with AURORA Learn for personalized learning roadmaps"""

from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from agents.base import Agent
from models.performance import Weakness, ConceptMastery
from models.roadmap import RoadmapUpdate, RoadmapTask
from models.academic import Concept
from utils.logger import logger
from config import settings


class RoadmapAgent(Agent):
    """Interfaces with AURORA Learn to update learning roadmaps"""
    
    def __init__(self, db: Session):
        super().__init__(agent_type="roadmap")
        self.db = db
        self.aurora_learn_url = getattr(settings, 'AURORA_LEARN_URL', 'http://localhost:8001')
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send roadmap update to AURORA Learn"""
        student_id = UUID(task_data["student_id"])
        subject_id = UUID(task_data.get("subject_id"))
        
        # Get weaknesses
        weaknesses = self.db.query(Weakness).join(Weakness.topic).join(
            Weakness.topic.unit
        ).filter(
            Weakness.student_id == student_id,
            Weakness.topic.unit.has(subject_id=subject_id)
        ).order_by(Weakness.severity.desc()).all()
        
        if not weaknesses:
            logger.info("No weaknesses found", extra={"student_id": str(student_id)})
            return {
                "student_id": str(student_id),
                "weaknesses_count": 0,
                "status": "no_update_needed"
            }
        
        # Format roadmap update
        update_payload = await self.format_roadmap_update(student_id, weaknesses)
        
        # Send to AURORA Learn
        try:
            result = await self.send_roadmap_update(update_payload)
            
            # Store roadmap update record
            roadmap_update = RoadmapUpdate(
                student_id=student_id,
                payload=update_payload,
                sent_at=datetime.utcnow(),
                acknowledged=result.get("acknowledged", False)
            )
            self.db.add(roadmap_update)
            self.db.commit()
            
            return {
                "student_id": str(student_id),
                "weaknesses_count": len(weaknesses),
                "status": "sent",
                "update_id": str(roadmap_update.id)
            }
            
        except Exception as e:
            logger.error("Failed to send roadmap update", extra={
                "student_id": str(student_id),
                "error": str(e)
            })
            return {
                "student_id": str(student_id),
                "weaknesses_count": len(weaknesses),
                "status": "failed",
                "error": str(e)
            }
    
    async def format_roadmap_update(
        self,
        student_id: UUID,
        weaknesses: List[Weakness]
    ) -> Dict[str, Any]:
        """Format roadmap update payload for AURORA Learn"""
        
        weakness_data = []
        
        for weakness in weaknesses:
            # Get concepts for this topic
            concepts = self.db.query(Concept).filter(
                Concept.topic_id == weakness.topic_id
            ).all()
            
            for concept in concepts:
                # Get concept mastery
                mastery = self.db.query(ConceptMastery).filter(
                    ConceptMastery.student_id == student_id,
                    ConceptMastery.concept_id == concept.id
                ).first()
                
                mastery_score = mastery.mastery_level if mastery else 0.0
                
                weakness_data.append({
                    "concept_id": str(concept.id),
                    "concept_name": concept.name,
                    "topic_id": str(weakness.topic_id),
                    "mastery_score": mastery_score,
                    "severity": weakness.severity,
                    "recommended_resources": weakness.recommended_resources
                })
        
        return {
            "student_id": str(student_id),
            "weaknesses": weakness_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def send_roadmap_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send roadmap update to AURORA Learn API"""
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.aurora_learn_url}/api/roadmap/update",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("HTTP error sending roadmap update", extra={
                    "error": str(e),
                    "status_code": getattr(e.response, 'status_code', None)
                })
                raise
    
    async def receive_roadmap_tasks(
        self,
        student_id: UUID,
        tasks: List[Dict[str, Any]]
    ) -> None:
        """Receive and store roadmap tasks from AURORA Learn"""
        
        for task_data in tasks:
            # Check if task already exists
            existing = self.db.query(RoadmapTask).filter(
                RoadmapTask.external_id == task_data.get("id")
            ).first()
            
            if existing:
                # Update existing task
                existing.title = task_data.get("title", existing.title)
                existing.description = task_data.get("description", existing.description)
                existing.completed = task_data.get("completed", existing.completed)
            else:
                # Create new task
                task = RoadmapTask(
                    student_id=student_id,
                    concept_id=UUID(task_data["concept_id"]) if task_data.get("concept_id") else None,
                    external_id=task_data.get("id"),
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    resources=task_data.get("resources", []),
                    due_date=datetime.fromisoformat(task_data["due_date"]) if task_data.get("due_date") else None,
                    completed=task_data.get("completed", False)
                )
                self.db.add(task)
        
        self.db.commit()
        
        logger.info("Roadmap tasks received", extra={
            "student_id": str(student_id),
            "task_count": len(tasks)
        })
    
    async def mark_task_complete(
        self,
        task_id: UUID,
        student_id: UUID
    ) -> None:
        """Mark a roadmap task as complete and update concept mastery"""
        
        task = self.db.query(RoadmapTask).filter(
            RoadmapTask.id == task_id,
            RoadmapTask.student_id == student_id
        ).first()
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.completed = True
        task.completed_at = datetime.utcnow()
        
        # Update concept mastery
        if task.concept_id:
            mastery = self.db.query(ConceptMastery).filter(
                ConceptMastery.student_id == student_id,
                ConceptMastery.concept_id == task.concept_id
            ).first()
            
            if mastery:
                # Increase mastery by 10% (capped at 1.0)
                mastery.mastery_level = min(mastery.mastery_level + 0.1, 1.0)
            else:
                # Create new mastery record
                mastery = ConceptMastery(
                    student_id=student_id,
                    concept_id=task.concept_id,
                    mastery_level=0.1
                )
                self.db.add(mastery)
        
        self.db.commit()
        
        logger.info("Roadmap task completed", extra={
            "task_id": str(task_id),
            "student_id": str(student_id)
        })
