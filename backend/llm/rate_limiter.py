"""
Rate Limiter for LLM API Calls

Implements token bucket algorithm for rate limiting both requests and tokens.
"""

import asyncio
import time
from typing import Optional
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    tokens_per_minute: int = 90000
    burst_multiplier: float = 1.5  # Allow bursts up to 1.5x the rate


class RateLimiter:
    """
    Token bucket rate limiter for LLM API calls.
    
    Tracks both request count and token usage to stay within API limits.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 90000,
        burst_multiplier: float = 1.5
    ):
        """
        Initialize rate limiter
        
        Args:
            requests_per_minute: Maximum requests per minute
            tokens_per_minute: Maximum tokens per minute
            burst_multiplier: Allow bursts up to this multiple of the rate
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.burst_multiplier = burst_multiplier
        
        # Token buckets
        self.max_requests = int(requests_per_minute * burst_multiplier)
        self.max_tokens = int(tokens_per_minute * burst_multiplier)
        
        self.available_requests = self.max_requests
        self.available_tokens = self.max_tokens
        
        # Refill rates (per second)
        self.request_refill_rate = requests_per_minute / 60.0
        self.token_refill_rate = tokens_per_minute / 60.0
        
        # Last refill time
        self.last_refill = time.time()
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
        
        logger.info(
            "Rate limiter initialized",
            extra={
                "requests_per_minute": requests_per_minute,
                "tokens_per_minute": tokens_per_minute,
                "max_requests": self.max_requests,
                "max_tokens": self.max_tokens
            }
        )

    async def acquire(self, tokens: int = 0) -> None:
        """
        Acquire permission to make an API call
        
        Blocks until sufficient capacity is available.
        
        Args:
            tokens: Number of tokens this request will use
        """
        async with self.lock:
            while True:
                # Refill buckets based on time elapsed
                self._refill()
                
                # Check if we have capacity
                if self.available_requests >= 1 and self.available_tokens >= tokens:
                    # Consume capacity
                    self.available_requests -= 1
                    self.available_tokens -= tokens
                    
                    logger.debug(
                        "Rate limit acquired",
                        extra={
                            "tokens_used": tokens,
                            "available_requests": self.available_requests,
                            "available_tokens": self.available_tokens
                        }
                    )
                    return
                
                # Calculate wait time
                wait_time = self._calculate_wait_time(tokens)
                
                logger.debug(
                    "Rate limit reached, waiting",
                    extra={
                        "wait_time_seconds": wait_time,
                        "available_requests": self.available_requests,
                        "available_tokens": self.available_tokens,
                        "requested_tokens": tokens
                    }
                )
                
                # Wait and try again
                await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Refill token buckets based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed > 0:
            # Refill requests
            request_refill = elapsed * self.request_refill_rate
            self.available_requests = min(
                self.max_requests,
                self.available_requests + request_refill
            )
            
            # Refill tokens
            token_refill = elapsed * self.token_refill_rate
            self.available_tokens = min(
                self.max_tokens,
                self.available_tokens + token_refill
            )
            
            self.last_refill = now

    def _calculate_wait_time(self, tokens: int) -> float:
        """
        Calculate how long to wait for capacity
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Wait time in seconds
        """
        # Time to refill requests
        request_wait = 0.0
        if self.available_requests < 1:
            requests_needed = 1 - self.available_requests
            request_wait = requests_needed / self.request_refill_rate
        
        # Time to refill tokens
        token_wait = 0.0
        if self.available_tokens < tokens:
            tokens_needed = tokens - self.available_tokens
            token_wait = tokens_needed / self.token_refill_rate
        
        # Wait for whichever takes longer
        wait_time = max(request_wait, token_wait)
        
        # Add small buffer
        return wait_time + 0.1

    async def get_stats(self) -> dict:
        """
        Get current rate limiter statistics
        
        Returns:
            Dictionary with current state
        """
        async with self.lock:
            self._refill()
            
            return {
                "available_requests": self.available_requests,
                "max_requests": self.max_requests,
                "available_tokens": self.available_tokens,
                "max_tokens": self.max_tokens,
                "request_utilization": 1 - (self.available_requests / self.max_requests),
                "token_utilization": 1 - (self.available_tokens / self.max_tokens)
            }

    def reset(self) -> None:
        """Reset rate limiter to full capacity"""
        self.available_requests = self.max_requests
        self.available_tokens = self.max_tokens
        self.last_refill = time.time()
        
        logger.info("Rate limiter reset")
