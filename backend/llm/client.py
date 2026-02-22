"""
LLM Client Wrapper

Provides a unified interface for interacting with multiple LLM providers
(OpenAI, Anthropic, etc.) with automatic fallback, retry logic, and logging.
"""

import asyncio
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import json

import openai
from openai import AsyncOpenAI
import anthropic
from anthropic import AsyncAnthropic
import tiktoken

from config import settings
from utils.logger import get_logger
from llm.rate_limiter import RateLimiter

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    FALLBACK = "fallback"


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    latency_ms: float
    finish_reason: str
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class LLMConfig:
    """Configuration for LLM client"""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    fallback_provider: Optional[LLMProvider] = LLMProvider.ANTHROPIC
    fallback_model: Optional[str] = "claude-3-sonnet-20240229"


class LLMClient:
    """
    Unified LLM client with support for multiple providers, automatic fallback,
    retry logic, rate limiting, and comprehensive logging.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize LLM client
        
        Args:
            config: LLM configuration (uses defaults if not provided)
        """
        self.config = config or LLMConfig()
        
        # Initialize API clients
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=self.config.timeout,
            max_retries=0  # We handle retries ourselves
        )
        
        self.anthropic_client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=self.config.timeout,
            max_retries=0
        )
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=90000
        )
        
        # Token encoder for counting
        self.token_encoder = tiktoken.encoding_for_model("gpt-4")
        
        logger.info(
            f"LLM client initialized",
            extra={
                "provider": self.config.provider.value,
                "model": self.config.model,
                "fallback_provider": self.config.fallback_provider.value if self.config.fallback_provider else None
            }
        )

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion from the LLM
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: Whether to request JSON output
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated content and metadata
            
        Raises:
            Exception: If all providers fail after retries
        """
        start_time = time.time()
        
        # Count tokens for rate limiting
        prompt_tokens = self.count_tokens(prompt)
        if system_prompt:
            prompt_tokens += self.count_tokens(system_prompt)
        
        # Wait for rate limit
        await self.rate_limiter.acquire(tokens=prompt_tokens)
        
        # Try primary provider
        try:
            response = await self._complete_with_retry(
                provider=self.config.provider,
                model=self.config.model,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                json_mode=json_mode,
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            response.latency_ms = latency_ms
            
            # Log successful completion
            self._log_completion(response, prompt, system_prompt, success=True)
            
            return response
            
        except Exception as e:
            logger.warning(
                f"Primary provider {self.config.provider.value} failed: {str(e)}",
                extra={"error": str(e), "provider": self.config.provider.value}
            )
            
            # Try fallback provider if configured
            if self.config.fallback_provider:
                try:
                    logger.info(f"Attempting fallback to {self.config.fallback_provider.value}")
                    
                    response = await self._complete_with_retry(
                        provider=self.config.fallback_provider,
                        model=self.config.fallback_model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature or self.config.temperature,
                        max_tokens=max_tokens or self.config.max_tokens,
                        json_mode=json_mode,
                        **kwargs
                    )
                    
                    latency_ms = (time.time() - start_time) * 1000
                    response.latency_ms = latency_ms
                    
                    # Log fallback completion
                    self._log_completion(response, prompt, system_prompt, success=True, fallback=True)
                    
                    return response
                    
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback provider also failed: {str(fallback_error)}",
                        extra={"error": str(fallback_error), "provider": self.config.fallback_provider.value}
                    )
                    raise Exception(f"All LLM providers failed. Primary: {str(e)}, Fallback: {str(fallback_error)}")
            
            # No fallback configured, raise original error
            raise

    async def _complete_with_retry(
        self,
        provider: LLMProvider,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        **kwargs
    ) -> LLMResponse:
        """
        Complete with exponential backoff retry logic
        
        Args:
            provider: LLM provider to use
            model: Model name
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature parameter
            max_tokens: Maximum tokens to generate
            json_mode: Whether to request JSON output
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                if provider == LLMProvider.OPENAI:
                    return await self._complete_openai(
                        model=model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                        **kwargs
                    )
                elif provider == LLMProvider.ANTHROPIC:
                    return await self._complete_anthropic(
                        model=model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                else:
                    raise ValueError(f"Unsupported provider: {provider}")
                    
            except Exception as e:
                last_error = e
                
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self.config.retry_delay * (2 ** attempt)
                    jitter = delay * 0.1
                    await asyncio.sleep(delay + jitter)
                    
                    logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{self.config.max_retries}), retrying...",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
        
        raise last_error

    async def _complete_openai(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        **kwargs
    ) -> LLMResponse:
        """Complete using OpenAI API"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        # Build request parameters
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        if json_mode:
            request_params["response_format"] = {"type": "json_object"}
        
        # Make API call
        response = await self.openai_client.chat.completions.create(**request_params)
        
        # Extract response data
        content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        tokens_used = response.usage.total_tokens
        
        return LLMResponse(
            content=content,
            provider=LLMProvider.OPENAI,
            model=model,
            tokens_used=tokens_used,
            latency_ms=0,  # Will be set by caller
            finish_reason=finish_reason,
            raw_response=response.model_dump()
        )

    async def _complete_anthropic(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> LLMResponse:
        """Complete using Anthropic API"""
        request_params = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs
        }
        
        if system_prompt:
            request_params["system"] = system_prompt
        
        # Make API call
        response = await self.anthropic_client.messages.create(**request_params)
        
        # Extract response data
        content = response.content[0].text
        finish_reason = response.stop_reason
        
        # Anthropic doesn't provide token counts in the same way
        # Estimate tokens
        tokens_used = self.count_tokens(prompt) + self.count_tokens(content)
        if system_prompt:
            tokens_used += self.count_tokens(system_prompt)
        
        return LLMResponse(
            content=content,
            provider=LLMProvider.ANTHROPIC,
            model=model,
            tokens_used=tokens_used,
            latency_ms=0,  # Will be set by caller
            finish_reason=finish_reason,
            raw_response=response.model_dump()
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            return len(self.token_encoder.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}, using character-based estimate")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

    def _log_completion(
        self,
        response: LLMResponse,
        prompt: str,
        system_prompt: Optional[str],
        success: bool,
        fallback: bool = False
    ):
        """
        Log LLM completion with all relevant metadata
        
        Args:
            response: LLM response
            prompt: User prompt
            system_prompt: System prompt
            success: Whether completion was successful
            fallback: Whether this was a fallback attempt
        """
        log_data = {
            "event": "llm_completion",
            "provider": response.provider.value,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "finish_reason": response.finish_reason,
            "success": success,
            "fallback": fallback,
            "prompt_length": len(prompt),
            "response_length": len(response.content),
            "prompt_tokens": self.count_tokens(prompt),
            "response_tokens": self.count_tokens(response.content)
        }
        
        if system_prompt:
            log_data["system_prompt_length"] = len(system_prompt)
            log_data["system_prompt_tokens"] = self.count_tokens(system_prompt)
        
        logger.info("LLM completion", extra=log_data)

    async def close(self):
        """Close API clients"""
        await self.openai_client.close()
        await self.anthropic_client.close()
