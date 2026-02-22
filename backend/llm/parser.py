"""
LLM Response Parser

Parses and validates LLM responses, especially JSON responses.
"""

import json
import re
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError

from utils.logger import get_logger

logger = get_logger(__name__)


class ResponseParser:
    """
    Parser for LLM responses with JSON extraction and validation
    """

    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response text
        
        Handles cases where JSON is embedded in markdown code blocks or
        surrounded by explanatory text.
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Parsed JSON dict or None if no valid JSON found
        """
        # Try direct JSON parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Try to find JSON object in text
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        logger.warning("No valid JSON found in response", extra={"text_preview": text[:200]})
        return None

    @staticmethod
    def parse_json(text: str, schema: Optional[Type[BaseModel]] = None) -> Dict[str, Any]:
        """
        Parse JSON from text and optionally validate against Pydantic schema
        
        Args:
            text: Response text containing JSON
            schema: Optional Pydantic model to validate against
            
        Returns:
            Parsed and validated JSON dict
            
        Raises:
            ValueError: If JSON cannot be extracted or is invalid
            ValidationError: If schema validation fails
        """
        # Extract JSON
        data = ResponseParser.extract_json(text)
        
        if data is None:
            raise ValueError("Could not extract valid JSON from response")
        
        # Validate against schema if provided
        if schema:
            try:
                validated = schema(**data)
                return validated.model_dump()
            except ValidationError as e:
                logger.error(
                    "Schema validation failed",
                    extra={"errors": e.errors(), "data": data}
                )
                raise
        
        return data

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text response
        
        Args:
            text: Raw text response
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove markdown artifacts
        text = re.sub(r'```[a-z]*\n?', '', text)
        
        # Trim
        text = text.strip()
        
        return text

    @staticmethod
    def extract_code_blocks(text: str, language: Optional[str] = None) -> list[str]:
        """
        Extract code blocks from markdown-formatted text
        
        Args:
            text: Text containing markdown code blocks
            language: Optional language filter (e.g., 'python', 'json')
            
        Returns:
            List of code block contents
        """
        if language:
            pattern = f'```{language}\\s*\\n(.*?)```'
        else:
            pattern = r'```(?:[a-z]+)?\s*\n(.*?)```'
        
        matches = re.findall(pattern, text, re.DOTALL)
        return [match.strip() for match in matches]

    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: list[str]) -> bool:
        """
        Validate that required fields are present in parsed data
        
        Args:
            data: Parsed data dictionary
            required_fields: List of required field names
            
        Returns:
            True if all required fields present, False otherwise
        """
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.warning(
                "Missing required fields in response",
                extra={"missing_fields": missing_fields, "data_keys": list(data.keys())}
            )
            return False
        
        return True

    @staticmethod
    def parse_list_response(text: str) -> list[str]:
        """
        Parse a list from LLM response
        
        Handles various list formats:
        - Numbered lists (1. item, 2. item)
        - Bullet lists (- item, * item)
        - Comma-separated
        - JSON arrays
        
        Args:
            text: Response text containing a list
            
        Returns:
            List of items
        """
        # Try JSON array first
        try:
            data = json.loads(text.strip())
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            pass
        
        # Try numbered list
        numbered_pattern = r'^\d+\.\s*(.+)$'
        matches = re.findall(numbered_pattern, text, re.MULTILINE)
        if matches:
            return [match.strip() for match in matches]
        
        # Try bullet list
        bullet_pattern = r'^[-*]\s*(.+)$'
        matches = re.findall(bullet_pattern, text, re.MULTILINE)
        if matches:
            return [match.strip() for match in matches]
        
        # Try comma-separated
        if ',' in text:
            items = text.split(',')
            return [item.strip() for item in items if item.strip()]
        
        # Try newline-separated
        lines = text.split('\n')
        items = [line.strip() for line in lines if line.strip()]
        if len(items) > 1:
            return items
        
        # Single item
        return [text.strip()]
