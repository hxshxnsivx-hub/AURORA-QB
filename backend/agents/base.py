"""
Base agent class for the multi-agent orchestration system.

All specialized agents inherit from this base class which provides
common functionality for task processing, error handling, and logging.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from utils.logger import logger


class AgentStatus(str, Enum):
    """Agent status enumeration"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPED = "stopped"


class Agent(ABC):
    """
    Base class for all agents in the system.
    
    Each agent must implement the process() method which contains
    the agent-specific logic for handling tasks.
    """
    
    def __init__(self, agent_type: str):
        """
        Initialize agent.
        
        Args:
            agent_type: Unique identifier for this agent type
        """
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.last_error: Optional[str] = None
        self.started_at: Optional[datetime] = None
    
    @abstractmethod
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task.
        
        This method must be implemented by each specialized agent.
        
        Args:
            task_data: Task data including payload and metadata
        
        Returns:
            Result dictionary with processing outcome
        
        Raises:
            Exception: If processing fails
        """
        pass
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task with error handling and logging.
        
        This method wraps the process() method with common functionality.
        
        Args:
            task_data: Task data to process
        
        Returns:
            Result dictionary
        """
        task_id = task_data.get("task_id", "unknown")
        
        try:
            self.status = AgentStatus.PROCESSING
            
            logger.info(f"{self.agent_type} processing task", extra={
                "agent_type": self.agent_type,
                "task_id": task_id,
                "status": self.status.value
            })
            
            # Call agent-specific processing logic
            result = await self.process(task_data)
            
            self.tasks_processed += 1
            self.status = AgentStatus.IDLE
            
            logger.info(f"{self.agent_type} task completed", extra={
                "agent_type": self.agent_type,
                "task_id": task_id,
                "tasks_processed": self.tasks_processed
            })
            
            return {
                "success": True,
                "result": result,
                "agent_type": self.agent_type,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.tasks_failed += 1
            self.last_error = str(e)
            self.status = AgentStatus.ERROR
            
            logger.error(f"{self.agent_type} task failed", extra={
                "agent_type": self.agent_type,
                "task_id": task_id,
                "error": str(e),
                "tasks_failed": self.tasks_failed
            })
            
            return {
                "success": False,
                "error": str(e),
                "agent_type": self.agent_type,
                "failed_at": datetime.utcnow().isoformat()
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status and statistics"""
        return {
            "agent_type": self.agent_type,
            "status": self.status.value,
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed,
            "last_error": self.last_error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "success_rate": (
                self.tasks_processed / (self.tasks_processed + self.tasks_failed)
                if (self.tasks_processed + self.tasks_failed) > 0
                else 0.0
            )
        }
    
    def reset_stats(self):
        """Reset agent statistics"""
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.last_error = None
        logger.info(f"{self.agent_type} stats reset", extra={
            "agent_type": self.agent_type
        })
    
    async def start(self):
        """Start the agent"""
        self.started_at = datetime.utcnow()
        self.status = AgentStatus.IDLE
        logger.info(f"{self.agent_type} started", extra={
            "agent_type": self.agent_type,
            "started_at": self.started_at.isoformat()
        })
    
    async def stop(self):
        """Stop the agent"""
        self.status = AgentStatus.STOPPED
        logger.info(f"{self.agent_type} stopped", extra={
            "agent_type": self.agent_type,
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed
        })
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"type={self.agent_type} "
            f"status={self.status.value} "
            f"processed={self.tasks_processed} "
            f"failed={self.tasks_failed}>"
        )
