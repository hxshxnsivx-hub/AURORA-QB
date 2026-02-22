"""
Retry logic with exponential backoff for agent tasks.

This module provides retry decorators and utilities for handling
transient failures in agent processing and external API calls.
"""

import asyncio
import functools
from typing import Callable, Optional, Tuple, Type
from datetime import datetime
import random

from utils.logger import logger


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter
    
    Returns:
        Delay in seconds
    """
    # Calculate exponential delay
    delay = min(base_delay * (exponential_base ** attempt), max_delay)
    
    # Add jitter to prevent thundering herd
    if jitter:
        delay = delay * (0.5 + random.random() * 0.5)
    
    return delay


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def fetch_data():
            # Code that might fail
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = calculate_backoff(
                            attempt,
                            base_delay=base_delay,
                            max_delay=max_delay,
                            exponential_base=exponential_base
                        )
                        
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{max_retries} for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay": delay,
                                "error": str(e)
                            }
                        )
                        
                        # Call retry callback if provided
                        if on_retry:
                            try:
                                if asyncio.iscoroutinefunction(on_retry):
                                    await on_retry(attempt, e, delay)
                                else:
                                    on_retry(attempt, e, delay)
                            except Exception as callback_error:
                                logger.error("Retry callback error", extra={
                                    "error": str(callback_error)
                                })
                        
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries exceeded for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "max_retries": max_retries,
                                "error": str(e)
                            }
                        )
            
            # All retries exhausted, raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


class RetryPolicy:
    """
    Retry policy configuration for agent tasks.
    
    This class encapsulates retry behavior and can be customized
    per agent or task type.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential calculation
            jitter: Whether to add random jitter
            retry_on: Tuple of exception types to retry on
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-indexed)
        
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False
        
        return isinstance(exception, self.retry_on)
    
    def get_delay(self, attempt: int) -> float:
        """
        Get delay for a specific attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        return calculate_backoff(
            attempt,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential_base=self.exponential_base,
            jitter=self.jitter
        )
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ):
        """
        Execute a function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of func
        
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                if not self.should_retry(e, attempt):
                    raise
                
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    
                    logger.warning("Retrying with policy", extra={
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "delay": delay,
                        "error": str(e)
                    })
                    
                    await asyncio.sleep(delay)
        
        raise last_exception


# Default retry policies for different scenarios

# Fast retry for quick operations
FAST_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0
)

# Standard retry for most operations
STANDARD_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0
)

# Slow retry for expensive operations
SLOW_RETRY = RetryPolicy(
    max_retries=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=2.0
)

# LLM API retry (handles rate limits)
LLM_RETRY = RetryPolicy(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0
)


class RetryStats:
    """Track retry statistics for monitoring"""
    
    def __init__(self):
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.total_delay = 0.0
    
    def record_attempt(self, success: bool, delay: float = 0.0):
        """Record a retry attempt"""
        self.total_attempts += 1
        if success:
            self.successful_retries += 1
        else:
            self.failed_retries += 1
        self.total_delay += delay
    
    def get_stats(self) -> dict:
        """Get retry statistics"""
        return {
            "total_attempts": self.total_attempts,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "success_rate": (
                self.successful_retries / self.total_attempts
                if self.total_attempts > 0
                else 0.0
            ),
            "average_delay": (
                self.total_delay / self.total_attempts
                if self.total_attempts > 0
                else 0.0
            )
        }
    
    def reset(self):
        """Reset statistics"""
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.total_delay = 0.0


# Global retry stats
retry_stats = RetryStats()
