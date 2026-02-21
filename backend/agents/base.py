"""
Base agent class with common functionality.

All specialized agents inherit from BaseAgent and implement:
- process() method for task execution
- validate_input() for input validation
- Agent-specific logic
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import AgentTask, AgentTaskStatus, AgentType
from agents.task_queue import AgentTaskManager
from utils.logger import logger


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, agent_type: AgentType):
        """
        Initialize agent
        
        Args:
            agent_type: Type of agent
        """
        self.agent_type = agent_type
        self.name = agent_type.value
    
    @abstractmethod
    async def process(
        self,
        db: AsyncSession,
        task: AgentTask
    ) -> Dict[str, Any]:
        """
        Process agent task (must be implemented by subclasses)
        
        Args:
            db: Database session
            task: Agent task to process
        
        Returns:
            Task output data
        
        Raises:
            Exception: If processing fails
        """
        pass
    
    @abstractmethod
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate task input data (must be implemented by subclasses)
        
        Args:
            input_data: Task input data
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If validation fails
        """
        pass
    
    async def execute(
        self,
        db: AsyncSession,
        task: AgentTask
    ) -> bool:
        """
        Execute task with error handling and status updates
        
        Args:
            db: Database session
            task: Agent task to execute
        
        Returns:
            True if successful
        """
        try:
            # Validate input
            await self.validate_input(task.input_data)
            
            # Update status to in progress
            await AgentTaskManager.update_task_status(
                db,
                task.id,
                AgentTaskStatus.IN_PROGRESS
            )
            
            logger.info(
                f"{self.name} started processing task",
                extra={
                    "task_id": task.id,
                    "agent_type": self.agent_type.value
                }
            )
            
            # Process task
            output_data = await self.process(db, task)
            
            # Update status to completed
            await AgentTaskManager.update_task_status(
                db,
                task.id,
                AgentTaskStatus.COMPLETED,
                output_data=output_data
            )
            
            logger.info(
                f"{self.name} completed task",
                extra={
                    "task_id": task.id,
                    "agent_type": self.agent_type.value
                }
            )
            
            return True
            
        except Exception as e:
            error_message = str(e)
            
            logger.error(
                f"{self.name} failed to process task",
                extra={
                    "task_id": task.id,
                    "agent_type": self.agent_type.value,
                    "error": error_message
                }
            )
            
            # Update status to failed
            await AgentTaskManager.update_task_status(
                db,
                task.id,
                AgentTaskStatus.FAILED,
                error_message=error_message
            )
            
            return False
    
    def log_progress(self, task_id: int, message: str, **kwargs):
        """
        Log agent progress
        
        Args:
            task_id: Task ID
            message: Progress message
            **kwargs: Additional log data
        """
        logger.info(
            f"{self.name}: {message}",
            extra={
                "task_id": task_id,
                "agent_type": self.agent_type.value,
                **kwargs
            }
        )
    
    def log_error(self, task_id: int, message: str, error: Exception):
        """
        Log agent error
        
        Args:
            task_id: Task ID
            message: Error message
            error: Exception object
        """
        logger.error(
            f"{self.name}: {message}",
            extra={
                "task_id": task_id,
                "agent_type": self.agent_type.value,
                "error": str(error),
                "error_type": type(error).__name__
            }
        )
