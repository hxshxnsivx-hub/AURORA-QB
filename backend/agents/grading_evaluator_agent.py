"""Grading Evaluator Agent - Evaluates student answers and generates feedback"""

from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from agents.base import Agent
from models.question import Question, QuestionType
from models.answer_key import AnswerKey
from models.attempt import Attempt, StudentAnswer
from models.evaluation import Evaluation
from llm.client import LLMClient
from utils.logger import logger


class GradingEvaluatorAgent(Agent):
    """Evaluates student answers and generates feedback"""
    
    def __init__(self, db: Session):
        super().__init__(agent_type="grading_evaluator")
        self.db = db
        self.llm_client = LLMClient()
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all answers in an attempt"""
        attempt_id = UUID(task_data["attempt_id"])
        
        # Get attempt
        attempt = self.db.query(Attempt).filter(Attempt.id == attempt_id).first()
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        
        # Get all student answers
        student_answers = self.db.query(StudentAnswer).filter(
            StudentAnswer.attempt_id == attempt_id
        ).all()
        
        total_score = 0.0
        evaluated_count = 0
        
        for student_answer in student_answers:
            try:
                score, feedback = await self.evaluate_answer(student_answer)
                
                # Create evaluation
                evaluation = Evaluation(
                    attempt_id=attempt_id,
                    question_id=student_answer.question_id,
                    score=score,
                    feedback=feedback,
                    evaluated_by_llm=(student_answer.question.type not in [
                        QuestionType.MCQ, QuestionType.TRUE_FALSE
                    ])
                )
                self.db.add(evaluation)
                
                total_score += score
                evaluated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to evaluate answer", extra={
                    "student_answer_id": str(student_answer.id),
                    "error": str(e)
                })
        
        # Update attempt with total score
        attempt.total_score = total_score
        attempt.status = "evaluated"
        
        self.db.commit()
        
        return {
            "attempt_id": str(attempt_id),
            "total_score": total_score,
            "evaluated_count": evaluated_count,
            "total_answers": len(student_answers)
        }
    
    async def evaluate_answer(
        self,
        student_answer: StudentAnswer
    ) -> tuple[float, str]:
        """Evaluate a single student answer"""
        
        question = student_answer.question
        answer_key = self.db.query(AnswerKey).filter(
            AnswerKey.question_id == question.id
        ).first()
        
        if not answer_key:
            raise ValueError(f"No answer key found for question {question.id}")
        
        # Route to appropriate grading method
        if question.type in [QuestionType.MCQ, QuestionType.TRUE_FALSE]:
            return self._grade_mcq(student_answer, answer_key)
        else:
            return await self._grade_with_llm(student_answer, answer_key)
    
    def _grade_mcq(
        self,
        student_answer: StudentAnswer,
        answer_key: AnswerKey
    ) -> tuple[float, str]:
        """Grade MCQ or True/False question"""
        
        student_text = (student_answer.answer_text or "").strip().lower()
        correct_answer = answer_key.model_answer.strip().lower()
        
        if student_text == correct_answer:
            score = float(student_answer.question.marks)
            feedback = "Correct answer!"
        else:
            score = 0.0
            feedback = f"Incorrect. The correct answer is: {answer_key.model_answer}"
        
        return score, feedback
    
    async def _grade_with_llm(
        self,
        student_answer: StudentAnswer,
        answer_key: AnswerKey
    ) -> tuple[float, str]:
        """Grade short/long answer using LLM"""
        
        question = student_answer.question
        
        # Build rubric text
        rubric_text = "\n".join([
            f"- {criterion['description']}: {criterion['points']} points"
            for criterion in answer_key.rubric["criteria"]
        ])
        
        prompt = f"""Grade this student answer using the provided rubric.

Question: {question.text}
Total Marks: {question.marks}

Model Answer:
{answer_key.model_answer}

Grading Rubric:
{rubric_text}

Student Answer:
{student_answer.answer_text or "(No answer provided)"}

Provide:
1. A score out of {question.marks}
2. Detailed feedback explaining the score

Respond in JSON format:
{{
  "score": <number between 0 and {question.marks}>,
  "feedback": "<detailed feedback>",
  "rubric_scores": [
    {{"criterion": "<criterion>", "points_awarded": <number>}},
    ...
  ]
}}"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=500
            )
            
            import json
            data = json.loads(response)
            
            score = float(data["score"])
            feedback = data["feedback"]
            
            # Validate score bounds
            if score < 0:
                score = 0.0
            elif score > question.marks:
                score = float(question.marks)
            
            # Add rubric breakdown to feedback
            if "rubric_scores" in data:
                feedback += "\n\nRubric Breakdown:\n"
                for item in data["rubric_scores"]:
                    feedback += f"- {item['criterion']}: {item['points_awarded']} points\n"
            
            return score, feedback
            
        except Exception as e:
            logger.error(f"LLM grading failed", extra={"error": str(e)})
            # Fallback: give partial credit
            score = float(question.marks) * 0.5
            feedback = "Automatic grading failed. Partial credit awarded. Please review manually."
            return score, feedback
    
    def calculate_total_score(self, attempt_id: UUID) -> float:
        """Calculate total score for an attempt"""
        
        evaluations = self.db.query(Evaluation).filter(
            Evaluation.attempt_id == attempt_id
        ).all()
        
        return sum(e.score for e in evaluations)
    
    def generate_feedback_summary(self, attempt_id: UUID) -> str:
        """Generate overall feedback summary"""
        
        evaluations = self.db.query(Evaluation).filter(
            Evaluation.attempt_id == attempt_id
        ).all()
        
        total_score = sum(e.score for e in evaluations)
        max_score = sum(e.question.marks for e in evaluations)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        summary = f"Total Score: {total_score}/{max_score} ({percentage:.1f}%)\n\n"
        
        if percentage >= 80:
            summary += "Excellent performance! "
        elif percentage >= 60:
            summary += "Good work! "
        else:
            summary += "Needs improvement. "
        
        return summary
