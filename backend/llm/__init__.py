"""
LLM Integration Layer

This module provides a unified interface for interacting with Large Language Models (LLMs)
including OpenAI, Anthropic, and other providers. It handles:
- API client management
- Prompt templating
- Token counting and rate limiting
- Response parsing and validation
- Retry logic and fallback providers
- Embedding generation
- Comprehensive logging
"""

from .client import LLMClient, LLMProvider
from .prompts import PromptTemplate, PromptRegistry
from .embeddings import EmbeddingGenerator
from .rate_limiter import RateLimiter
from .parser import ResponseParser

__all__ = [
    "LLMClient",
    "LLMProvider",
    "PromptTemplate",
    "PromptRegistry",
    "EmbeddingGenerator",
    "RateLimiter",
    "ResponseParser",
]
