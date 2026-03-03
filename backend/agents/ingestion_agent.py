"""
Ingestion & Tagging Agent

This agent handles:
1. File parsing (PDF, DOCX, TXT)
2. Question extraction with LLM-based boundary detection
3. LLM-based tag suggestion (unit, topic, marks, type, difficulty)
4. Question storage with embeddings
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import os

from agents.base import Agent
from parsers.pdf_parser import PDFParser
from parsers.docx_parser import DOCXParser
from parsers.txt_parser import TXTParser
from parsers.question_extractor import QuestionExtractor
from llm.client import LLMClient
from llm.embeddings import generate_embedding
from models.question import Question, QuestionBank, QuestionBankStatus, QuestionType, DifficultyLevel
from utils.logger import logger
from utils.storage import download_file
from sqlalchemy.orm import Session


class IngestionAgent(Agent):
    """
    Agent responsible for ingesting question banks and extracting questions.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the Ingestion Agent.
        
        Args:
            db: Database session
        """
        super().__init__(agent_type="ingestion")
        self.db = db
        self.llm_client = LLMClient()
        self.question_extractor = QuestionExtractor()
        
        # Initialize parsers
        self.parsers = {
            '.pdf': PDFParser(),
            '.docx': DOCXParser(),
            '.txt': TXTParser()
        }
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a question bank file.
        
        Args:
            task_data: Contains bank_id
        
        Returns:
            Result with extracted questions count
        """
        bank_id = task_data.get("bank_id")
        
        if not bank_id:
            raise ValueError("bank_id is required")
        
        # Get question bank from database
        bank = self.db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
        
        if not bank:
            raise ValueError(f"Question bank {bank_id} not found")
        
        try:
            # Update status to processing
            bank.status = QuestionBankStatus.PROCESSING
            self.db.commit()
            
            # Download file from storage
            local_path = await download_file(bank.file_path)
            
            # Parse file based on extension
            file_ext = os.path.splitext(bank.file_name)[1].lower()
            
            if file_ext not in self.parsers:
                raise ValueError(f"Unsupported file format: {file_ext}")
            
            parser = self.parsers[file_ext]
            raw_text = await parser.parse(local_path)
            
            # Extract questions with LLM-based boundary detection
            questions_text = await self._extract_questions_with_llm(raw_text)
            
            # Process each question
            extracted_count = 0
            for question_text in questions_text:
                try:
                    # Suggest tags using LLM
                    tags = await self._suggest_tags(question_text, bank.subject_id)
                    
                    # Generate embedding
                    embedding = await generate_embedding(question_text)
                    
                    # Store question
                    question = Question(
                        bank_id=bank.id,
                        text=question_text,
                        marks=tags.get("marks", 1),
                        type=QuestionType(tags.get("type", "Short Answer")),
                        difficulty=DifficultyLevel(tags.get("difficulty", "Medium")),
                        unit_id=tags.get("unit_id"),
                        topic_id=tags.get("topic_id"),
                        embedding=embedding,
                        tags_confirmed=False
                    )
                    
                    self.db.add(question)
                    extracted_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process question", extra={
                        "bank_id": str(bank_id),
                        "error": str(e),
                        "question_preview": question_text[:100]
                    })
                    continue
            
            # Update bank status
            bank.status = QuestionBankStatus.COMPLETED
            self.db.commit()
            
            # Clean up local file
            if os.path.exists(local_path):
                os.remove(local_path)
            
            logger.info(f"Question bank processed successfully", extra={
                "bank_id": str(bank_id),
                "questions_extracted": extracted_count
            })
            
            return {
                "bank_id": str(bank_id),
                "questions_extracted": extracted_count,
                "status": "completed"
            }
            
        except Exception as e:
            # Update bank status to failed
            bank.status = QuestionBankStatus.FAILED
            bank.processing_error = str(e)
            self.db.commit()
            
            logger.error(f"Question bank processing failed", extra={
                "bank_id": str(bank_id),
                "error": str(e)
            })
            
            raise
    
    async def _extract_questions_with_llm(self, raw_text: str) -> List[str]:
        """
        Extract individual questions from raw text using LLM-based boundary detection.
        
        Args:
            raw_text: Raw text from parsed file
        
        Returns:
            List of individual question texts
        """
        # First try pattern-based extraction
        questions = self.question_extractor.extract_questions(raw_text)
        
        # If pattern-based extraction yields few results, use LLM
        if len(questions) < 3:
            logger.info("Using LLM for question boundary detection")
            questions = await self._llm_question_detection(raw_text)
        
        return questions
    
    async def _llm_question_detection(self, raw_text: str) -> List[str]:
        """
        Use LLM to detect question boundaries in text.
        
        Args:
            raw_text: Raw text from file
        
        Returns:
            List of individual questions
        """
        prompt = f"""You are analyzing exam questions from a question bank file.

Text:
{raw_text[:4000]}  # Limit to avoid token limits

Your task is to identify individual questions and their boundaries.
Each question should be complete with all its parts (sub-questions, options, etc.).

Return a JSON array of questions:
[
  {{"question": "Question 1 text..."}},
  {{"question": "Question 2 text..."}},
  ...
]

Only include the question text, not answers or solutions."""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse JSON response
            import json
            questions_data = json.loads(response)
            
            return [q["question"] for q in questions_data if "question" in q]
            
        except Exception as e:
            logger.error(f"LLM question detection failed", extra={"error": str(e)})
            # Fallback to pattern-based extraction
            return self.question_extractor.extract_questions(raw_text)
    
    async def _suggest_tags(self, question_text: str, subject_id: UUID) -> Dict[str, Any]:
        """
        Use LLM to suggest tags for a question.
        
        Args:
            question_text: Question text
            subject_id: Subject ID for context
        
        Returns:
            Dictionary with suggested tags
        """
        prompt = f"""You are analyzing an exam question to extract metadata.

Question: {question_text}

Extract the following information:
1. Marks: Estimated marks for this question (1, 2, 3, 5, 10, or 12)
2. Type: MCQ, Short Answer, Long Answer, Numerical, or True/False
3. Difficulty: Easy, Medium, or Hard
4. Topic: Main topic covered (be specific)
5. Unit: Broader unit or chapter

Respond in JSON format:
{{
  "marks": <number>,
  "type": "<type>",
  "difficulty": "<difficulty>",
  "topic": "<topic>",
  "unit": "<unit>"
}}"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse JSON response
            import json
            tags = json.loads(response)
            
            # Validate and normalize
            tags["marks"] = int(tags.get("marks", 1))
            tags["type"] = tags.get("type", "Short Answer")
            tags["difficulty"] = tags.get("difficulty", "Medium")
            
            # TODO: Map topic/unit strings to database IDs
            # For now, leave as None - faculty will tag manually
            tags["unit_id"] = None
            tags["topic_id"] = None
            
            return tags
            
        except Exception as e:
            logger.error(f"LLM tag suggestion failed", extra={"error": str(e)})
            # Return default tags
            return {
                "marks": 1,
                "type": "Short Answer",
                "difficulty": "Medium",
                "unit_id": None,
                "topic_id": None
            }
