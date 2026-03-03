"""Answer Key Generator Agent - Generates model answers and grading rubrics"""

from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from agents.base import Agent
from models.question import Question, QuestionType
from models.answer_key import AnswerKey, GradingRubric
from models.resource import Resource
from llm.client import LLMClient
from llm.embeddings import cosine_similarity
from utils.logger import logger


class AnswerKeyGeneratorAgent(Agent):
    """Generates answer keys with model answers and rubrics"""
    
    def __init__(self, db: Session):
        super().__init__(agent_type="answer_key_generator")
        self.db = db
        self.llm_client = LLMClient()
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate answer keys for a paper"""
        paper_id = UUID(task_data["paper_id"])
        
        # Get all questions in paper
        from models.paper import PaperQuestion
        paper_questions = self.db.query(PaperQuestion).filter(
            PaperQuestion.paper_id == paper_id
        ).all()
        
        generated_count = 0
        for pq in paper_questions:
            try:
                await self.generate_answer_key(pq.question_id)
                generated_count += 1
            except Exception as e:
                logger.error(f"Failed to generate answer key", extra={
                    "question_id": str(pq.question_id),
                    "error": str(e)
                })
        
        return {
            "paper_id": str(paper_id),
            "generated_count": generated_count,
            "total_questions": len(paper_questions)
        }
    
    async def generate_answer_key(self, question_id: UUID) -> AnswerKey:
        """Generate answer key for a question"""
        question = self.db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise ValueError(f"Question {question_id} not found")
        
        # Check if answer key already exists
        existing = self.db.query(AnswerKey).filter(
            AnswerKey.question_id == question_id
        ).first()
        
        if existing:
            return existing
        
        # Generate based on question type
        if question.type in [QuestionType.MCQ, QuestionType.TRUE_FALSE]:
            model_answer = question.correct_answer or "Answer not provided"
            rubric = self._create_simple_rubric(question.marks)
            citations = []
        else:
            # Use LLM for short/long answers
            resources = await self._get_relevant_resources(question)
            model_answer, rubric, citations = await self._generate_with_llm(
                question, resources
            )
        
        # Create answer key
        answer_key = AnswerKey(
            question_id=question_id,
            model_answer=model_answer,
            rubric=rubric,
            resource_citations=citations,
            reviewed_by_faculty=False
        )
        
        self.db.add(answer_key)
        self.db.commit()
        self.db.refresh(answer_key)
        
        return answer_key
    
    def _create_simple_rubric(self, marks: int) -> Dict:
        """Create simple rubric for MCQ/True-False"""
        return {
            "criteria": [
                {
                    "description": "Correct answer",
                    "points": marks
                }
            ]
        }
    
    async def _get_relevant_resources(self, question: Question) -> List[Resource]:
        """Get relevant resources for a question using semantic search"""
        if not question.embedding or not question.topic_id:
            return []
        
        # Get resources for the topic
        from models.resource import ResourceTopicLink
        resource_links = self.db.query(ResourceTopicLink).filter(
            ResourceTopicLink.topic_id == question.topic_id
        ).limit(5).all()
        
        resources = []
        for link in resource_links:
            resource = self.db.query(Resource).filter(
                Resource.id == link.resource_id
            ).first()
            if resource:
                resources.append(resource)
        
        return resources
    
    async def _generate_with_llm(
        self,
        question: Question,
        resources: List[Resource]
    ) -> tuple[str, Dict, List[str]]:
        """Generate model answer and rubric using LLM"""
        
        # Prepare resource excerpts
        resource_text = "\n\n".join([
            f"Resource {i+1}: {r.title}\n{r.content[:500] if hasattr(r, 'content') else 'Content not available'}"
            for i, r in enumerate(resources[:3])
        ])
        
        prompt = f"""Generate a model answer and grading rubric for this exam question.

Question: {question.text}
Marks: {question.marks}
Type: {question.type.value}

Relevant Resources:
{resource_text if resource_text else "No resources available"}

Generate:
1. A comprehensive model answer (grounded in the provided resources if available)
2. A grading rubric breaking down point allocation

Respond in JSON format:
{{
  "model_answer": "<detailed answer>",
  "rubric": {{
    "criteria": [
      {{"description": "<criterion>", "points": <number>}},
      ...
    ]
  }},
  "citations": ["<resource_id>", ...]
}}"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            import json
            data = json.loads(response)
            
            # Validate rubric points sum to question marks
            total_points = sum(c["points"] for c in data["rubric"]["criteria"])
            if total_points != question.marks:
                # Adjust proportionally
                factor = question.marks / total_points
                for criterion in data["rubric"]["criteria"]:
                    criterion["points"] = round(criterion["points"] * factor, 1)
            
            return (
                data["model_answer"],
                data["rubric"],
                [str(r.id) for r in resources]
            )
            
        except Exception as e:
            logger.error(f"LLM answer generation failed", extra={"error": str(e)})
            # Fallback
            return (
                "Model answer generation failed. Please review manually.",
                self._create_simple_rubric(question.marks),
                []
            )
