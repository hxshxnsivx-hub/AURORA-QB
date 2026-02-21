"""
Retry logic with exponential backoff for agent tasks.

Implements:
- Configurable retry attempts
- Exponential backoff calculation
- Max retry limits
- Jitter to prevent thundering herd
"""

import asyncio
import random
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import AgentTask, AgentTaskStatus
from agents.task_queue import AgentTaskManager, TaskQueue
from utils.logger import logger


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 300.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff (2.0 = double each time)
            jitter: Add random jitter to prevent thundering herd
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt using exponential backoff
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter (random 0-25% of delay)
        if self.jitter:
            jitter_amount = delay * 0.25 * random.random()
            delay += jitter_amount
        
        return delay
    
    def should_retry(self, attempt: int) -> bool:
        """
        Check if task should be retried
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            True if should retry
        """
        return attempt < self.max_attempts


class RetryManager:
    """Manages task retry logic"""
    
    # Default retry configuration
    DEFAULT_CONFIG = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=300.0,
        exponential_base=2.0,
        jitter=True
    )
    
    @staticmethod
    async def retry_task(
        db: AsyncSession,
        task_id: int,
        config: Optional[RetryConfig] = None
    ) -> bool:
        """
        Retry a failed task with exponential backoff
        
        Args:
            db: Database session
            task_id: Task ID to retry
            config: Retry configuration (uses default if None)
        
        Returns:
            True if retry scheduled
        """
        if config is None:
            config = RetryManager.DEFAULT_CONFIG
        
        try:
            # Get task
            task = await AgentTaskManager.get_task(db, task_id)
            
            if not task:
                logger.error(
                    "Task not found for retry",
                    extra={"task_id": task_id}
                )
                return False
            
            # Check if should retry
            if not config.should_retry(task.retry_count):
                logger.warning(
                    "Task exceeded max retry attempts",
                    extra={
                        "task_id": task_id,
                        "retry_count": task.retry_count,
                        "max_attempts": config.max_attempts
                    }
                )
                return False
            
            # Calculate delay
            delay = config.calculate_delay(task.retry_count)
            
            logger.info(
                "Scheduling task retry",
                extra={
                    "task_id": task_id,
                    "retry_count": task.retry_count + 1,
                    "delay_seconds": delay
                }
            )
            
            # Schedule retry after delay
            asyncio.create_task(
                RetryManager._delayed_retry(db, task_id, delay)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to schedule retry",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
            return False
    
    @staticmethod
    async def _delayed_retry(
        db: AsyncSession,
        task_id: int,
        delay: float
    ):
        """
        Execute delayed retry
        
        Args:
            db: Database session
            task_id: Task ID
            delay: Delay in seconds
        """
        try:
            # Wait for delay
            await asyncio.sleep(delay)
            
            # Retry task
            success = await AgentTaskManager.retry_task(db, task_id)
            
            if success:
                logger.info(
                    "Task retry executed",
                    extra={"task_id": task_id}
                )
            else:
                logger.error(
                    "Task retry failed",
                    extra={"task_id": task_id}
                )
                
        except Exception as e:
            logger.error(
                "Delayed retry error",
                extra={
                    "task_id": task_id,
                    "error": str(e)
                }
            )
    
    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """
        Retry a function with exponential backoff
        
        Args:
            func: Async function to retry
            *args: Function arguments
            config: Retry configuration
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retries fail
        """
        if config is None:
            config = RetryManager.DEFAULT_CONFIG
        
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                # Try to execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success
                if attempt > 0:
                    logger.info(
                        "Function succeeded after retry",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1
                        }
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                logger.warning(
                    "Function failed, will retry",
                    extra={
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_attempts": config.max_attempts,
                        "error": str(e)
                    }
                )
                
                # Check if should retry
                if not config.should_retry(attempt):
                    break
                
                # Calculate and wait for delay
                delay = config.calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(
            "Function failed after all retries",
            extra={
                "function": func.__name__,
                "attempts": config.max_attempts,
                "error": str(last_exception)
            }
        )
        
        raise last_exception
    
    @staticmethod
    async def retry_failed_tasks(
        db: AsyncSession,
        since: Optional[datetime] = None,
        config: Optional[RetryConfig] = None
    ) -> int:
        """
        Retry all failed tasks
        
        Args:
            db: Database session
            since: Only retry tasks failed after this time
            config: Retry configuration
        
        Returns:
            Number of tasks scheduled for retry
        """
        if config is None:
            config = RetryManager.DEFAULT_CONFIG
        
        try:
            # Get failed tasks
            failed_tasks = await AgentTaskManager.get_failed_tasks(
                db,
                since=since,
                limit=100
            )
            
            retry_count = 0
            
            for task in failed_tasks:
                # Check if should retry
                if config.should_retry(task.retry_count):
                    success = await RetryManager.retry_task(db, task.id, config)
                    if success:
                        retry_count += 1
            
            logger.info(
                "Batch retry completed",
                extra={
                    "total_failed": len(failed_tasks),
                    "retried": retry_count
                }
            )
            
            return retry_count
            
        except Exception as e:
            logger.error(
                "Batch retry failed",
                extra={"error": str(e)}
            )
            return 0


# Decorator for automatic retry
def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to async functions
    
    Args:
        config: Retry configuration
    
    Example:
        @with_retry(RetryConfig(max_attempts=5))
        async def my_function():
            # Function code
            pass
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            return await RetryManager.retry_with_backoff(
                func,
                *args,
                config=config,
                **kwargs
            )
        return wrapper
    return decorator
