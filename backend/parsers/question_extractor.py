"""
Question Extractor

Extracts individual questions from parsed text using pattern matching
and LLM-based boundary detection.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from llm.client import LLMClient, LLMConfig
from llm.prompts import QUESTION_BOUNDARY_PROMPT, TAG_SUGGESTION_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedQuestion:
    """Represents an extracted question with metadata"""
    text: str
    suggested_marks: Optional[int] = None
    suggested_type: Optional[str] = None
    suggested_difficulty: Optional[str] = None
    suggested_topic: Optional[str] = None
    suggested_unit: Optional[str] = None
    extraction_method: str = "pattern"  # "pattern" or "llm"


class QuestionExtractor:
    """
    Extracts questions from text using pattern matching and LLM assistance
    """
    
    # Common question number patterns
    QUESTION_PATTERNS = [
        r'^\s*(?:Q|Question|QUESTION)[\s.:-]*(\d+)',  # Q1, Question 1, etc.
        r'^\s*(\d+)[\s.:-]+',  # 1. or 1) at start of line
        r'^\s*\((\d+)\)',  # (1)
        r'^\s*\[(\d+)\]',  # [1]
    ]
    
    # Marks patterns
    MARKS_PATTERNS = [
        r'\[(\d+)\s*marks?\]',
        r'\((\d+)\s*marks?\)',
        r'(\d+)\s*marks?',
        r'\[(\d+)\s*M\]',
        r'\((\d+)\s*M\)',
    ]
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize question extractor
        
        Args:
            llm_client: Optional LLM client for boundary detection and tagging
        """
        self.llm_client = llm_client or LLMClient(LLMConfig())
    
    async def extract_questions(
        self,
        text: str,
        use_llm: bool = True
    ) -> List[ExtractedQuestion]:
        """
        Extract questions from text
        
        Args:
            text: Parsed text content
            use_llm: Whether to use LLM for boundary detection
            
        Returns:
            List of extracted questions
        """
        logger.info("Extracting questions from text")
        
        # First try pattern-based extraction
        questions = self._extract_with_patterns(text)
        
        # If pattern extraction yields few results and LLM is enabled, use LLM
        if len(questions) < 3 and use_llm:
            logger.info("Pattern extraction yielded few results, using LLM for boundary detection")
            questions = await self._extract_with_llm(text)
        
        logger.info(
            f"Extracted {len(questions)} questions",
            extra={
                "num_questions": len(questions),
                "extraction_method": questions[0].extraction_method if questions else "none"
            }
        )
        
        return questions
    
    def _extract_with_patterns(self, text: str) -> List[ExtractedQuestion]:
        """
        Extract questions using regex patterns
        
        Args:
            text: Text content
            
        Returns:
            List of extracted questions
        """
        questions = []
        lines = text.split('\n')
        
        current_question = []
        current_question_num = None
        
        for line in lines:
            # Check if line starts a new question
            is_question_start = False
            question_num = None
            
            for pattern in self.QUESTION_PATTERNS:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    is_question_start = True
                    question_num = match.group(1)
                    break
            
            if is_question_start:
                # Save previous question if exists
                if current_question:
                    question_text = '\n'.join(current_question).strip()
                    if question_text:
                        questions.append(self._create_question(question_text))
                
                # Start new question
                current_question = [line]
                current_question_num = question_num
            else:
                # Continue current question
                if current_question or line.strip():
                    current_question.append(line)
        
        # Don't forget the last question
        if current_question:
            question_text = '\n'.join(current_question).strip()
            if question_text:
                questions.append(self._create_question(question_text))
        
        return questions
    
    def _create_question(self, text: str) -> ExtractedQuestion:
        """
        Create ExtractedQuestion with basic metadata extraction
        
        Args:
            text: Question text
            
        Returns:
            ExtractedQuestion object
        """
        # Try to extract marks
        marks = None
        for pattern in self.MARKS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    marks = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    pass
        
        return ExtractedQuestion(
            text=text,
            suggested_marks=marks,
            extraction_method="pattern"
        )
    
    async def _extract_with_llm(self, text: str) -> List[ExtractedQuestion]:
        """
        Extract questions using LLM for boundary detection
        
        Args:
            text: Text content
            
        Returns:
            List of extracted questions
        """
        try:
            # Use LLM to identify question boundaries
            response = await self.llm_client.complete(
                prompt=QUESTION_BOUNDARY_PROMPT.format(text=text),
                json_mode=True,
                temperature=0.3
            )
            
            # Parse LLM response
            import json
            result = json.loads(response.content)
            
            questions = []
            for q in result.get("questions", []):
                questions.append(ExtractedQuestion(
                    text=q.get("text", ""),
                    suggested_marks=q.get("marks"),
                    extraction_method="llm"
                ))
            
            return questions
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            # Fallback to pattern-based extraction
            return self._extract_with_patterns(text)
    
    async def suggest_tags(
        self,
        question_text: str
    ) -> Dict[str, Any]:
        """
        Suggest tags for a question using LLM
        
        Args:
            question_text: Question text
            
        Returns:
            Dictionary with suggested tags
        """
        try:
            logger.info("Generating tag suggestions for question")
            
            response = await self.llm_client.complete(
                prompt=TAG_SUGGESTION_PROMPT.format(question_text=question_text),
                json_mode=True,
                temperature=0.3
            )
            
            # Parse LLM response
            import json
            tags = json.loads(response.content)
            
            logger.info(
                "Generated tag suggestions",
                extra={
                    "marks": tags.get("marks"),
                    "type": tags.get("type"),
                    "difficulty": tags.get("difficulty")
                }
            )
            
            return tags
            
        except Exception as e:
            logger.error(f"Tag suggestion failed: {str(e)}")
            raise Exception(f"Failed to generate tag suggestions: {str(e)}")
