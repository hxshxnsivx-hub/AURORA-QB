"""
Prompt Template System

Provides a structured way to manage and render prompts for LLM interactions.
"""

from typing import Any, Dict, Optional
from string import Template
from enum import Enum

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PromptType(str, Enum):
    """Types of prompts used in the system"""
    QUESTION_TAGGING = "question_tagging"
    ANSWER_GENERATION = "answer_generation"
    RUBRIC_GENERATION = "rubric_generation"
    ANSWER_GRADING = "answer_grading"
    QUESTION_EXTRACTION = "question_extraction"


class PromptTemplate:
    """
    Template for LLM prompts with variable substitution
    """

    def __init__(
        self,
        name: str,
        template: str,
        system_prompt: Optional[str] = None,
        required_vars: Optional[list] = None,
        description: Optional[str] = None
    ):
        """
        Initialize prompt template
        
        Args:
            name: Template name/identifier
            template: Template string with ${variable} placeholders
            system_prompt: Optional system prompt
            required_vars: List of required variable names
            description: Template description
        """
        self.name = name
        self.template = Template(template)
        self.system_prompt = system_prompt
        self.required_vars = required_vars or []
        self.description = description

    def render(self, **kwargs) -> str:
        """
        Render template with provided variables
        
        Args:
            **kwargs: Variables to substitute in template
            
        Returns:
            Rendered prompt string
            
        Raises:
            ValueError: If required variables are missing
        """
        # Check required variables
        missing_vars = [var for var in self.required_vars if var not in kwargs]
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")
        
        try:
            rendered = self.template.safe_substitute(**kwargs)
            
            logger.debug(
                f"Rendered prompt template: {self.name}",
                extra={
                    "template_name": self.name,
                    "variables": list(kwargs.keys()),
                    "rendered_length": len(rendered)
                }
            )
            
            return rendered
            
        except Exception as e:
            logger.error(f"Failed to render template {self.name}: {e}")
            raise

    def get_system_prompt(self) -> Optional[str]:
        """Get system prompt for this template"""
        return self.system_prompt


class PromptRegistry:
    """
    Central registry for all prompt templates used in the system
    """

    def __init__(self):
        """Initialize prompt registry with default templates"""
        self.templates: Dict[str, PromptTemplate] = {}
        self._register_default_templates()

    def _register_default_templates(self):
        """Register all default prompt templates"""
        
        # Question Tagging Template
        self.register(PromptTemplate(
            name=PromptType.QUESTION_TAGGING,
            system_prompt="You are analyzing an exam question to extract metadata.",
            template="""Question: ${question_text}

Extract the following information:
1. Marks: Estimated marks for this question (1, 2, 3, 5, 10, or 12)
2. Type: MCQ, Short Answer, Long Answer, Numerical, or True/False
3. Difficulty: Easy, Medium, or Hard
4. Topic: Main topic covered (be specific)
5. Unit: Broader unit or chapter

Respond in JSON format:
{
  "marks": <number>,
  "type": "<type>",
  "difficulty": "<difficulty>",
  "topic": "<topic>",
  "unit": "<unit>"
}""",
            required_vars=["question_text"],
            description="Extract metadata tags from a question"
        ))
        
        # Answer Generation Template
        self.register(PromptTemplate(
            name=PromptType.ANSWER_GENERATION,
            system_prompt="You are generating a model answer for an exam question.",
            template="""Question: ${question_text}
Marks: ${marks}
Type: ${question_type}

Relevant Resources:
${resource_excerpts}

Generate:
1. A comprehensive model answer (grounded in the provided resources)
2. A grading rubric breaking down point allocation

Format your response as JSON:
{
  "model_answer": "<detailed answer>",
  "rubric": {
    "criteria": [
      {"description": "<criterion>", "points": <number>},
      ...
    ]
  },
  "citations": ["<resource_id>", ...]
}""",
            required_vars=["question_text", "marks", "question_type", "resource_excerpts"],
            description="Generate model answer and rubric for a question"
        ))
        
        # Rubric Generation Template
        self.register(PromptTemplate(
            name=PromptType.RUBRIC_GENERATION,
            system_prompt="You are creating a grading rubric for an exam question.",
            template="""Question: ${question_text}
Marks: ${marks}
Type: ${question_type}

Create a detailed grading rubric that breaks down how the ${marks} marks should be allocated.
Each criterion should specify what the student needs to demonstrate and how many points it's worth.

Respond in JSON format:
{
  "criteria": [
    {"description": "<what to look for>", "points": <number>},
    ...
  ]
}

Ensure the points sum to exactly ${marks}.""",
            required_vars=["question_text", "marks", "question_type"],
            description="Generate grading rubric for a question"
        ))
        
        # Answer Grading Template
        self.register(PromptTemplate(
            name=PromptType.ANSWER_GRADING,
            system_prompt="You are grading a student's answer to an exam question.",
            template="""Question: ${question_text}
Marks: ${marks}

Model Answer:
${model_answer}

Grading Rubric:
${rubric_json}

Student Answer:
${student_answer}

Evaluate the student's answer against the rubric. For each criterion:
1. Determine if the student met the criterion (fully, partially, or not at all)
2. Assign points accordingly
3. Provide specific feedback

Respond in JSON format:
{
  "criterion_scores": [
    {
      "criterion": "<description>",
      "max_points": <number>,
      "awarded_points": <number>,
      "feedback": "<specific feedback>"
    },
    ...
  ],
  "total_score": <number>,
  "overall_feedback": "<summary feedback>"
}""",
            required_vars=["question_text", "marks", "model_answer", "rubric_json", "student_answer"],
            description="Grade a student answer against model answer and rubric"
        ))
        
        # Question Extraction Template
        self.register(PromptTemplate(
            name=PromptType.QUESTION_EXTRACTION,
            system_prompt="You are extracting individual questions from an exam paper.",
            template="""The following text contains multiple exam questions. Extract each question as a separate item.

Text:
${document_text}

For each question, identify:
1. The question number (if present)
2. The complete question text
3. Any sub-parts (a, b, c, etc.)
4. Marks indicated (if present)

Respond in JSON format:
{
  "questions": [
    {
      "number": "<question number>",
      "text": "<complete question text>",
      "marks": <number or null>,
      "has_subparts": <boolean>
    },
    ...
  ]
}""",
            required_vars=["document_text"],
            description="Extract individual questions from a document"
        ))

    def register(self, template: PromptTemplate) -> None:
        """
        Register a new prompt template
        
        Args:
            template: PromptTemplate to register
        """
        self.templates[template.name] = template
        logger.debug(f"Registered prompt template: {template.name}")

    def get(self, name: str) -> PromptTemplate:
        """
        Get a prompt template by name
        
        Args:
            name: Template name
            
        Returns:
            PromptTemplate
            
        Raises:
            KeyError: If template not found
        """
        if name not in self.templates:
            raise KeyError(f"Prompt template not found: {name}")
        
        return self.templates[name]

    def render(self, name: str, **kwargs) -> tuple[str, Optional[str]]:
        """
        Render a prompt template
        
        Args:
            name: Template name
            **kwargs: Variables for template
            
        Returns:
            Tuple of (rendered_prompt, system_prompt)
        """
        template = self.get(name)
        rendered = template.render(**kwargs)
        system_prompt = template.get_system_prompt()
        
        return rendered, system_prompt

    def list_templates(self) -> list[str]:
        """
        List all registered template names
        
        Returns:
            List of template names
        """
        return list(self.templates.keys())


# Global prompt registry instance
prompt_registry = PromptRegistry()
