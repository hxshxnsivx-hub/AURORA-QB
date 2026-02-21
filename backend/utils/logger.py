import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """Configure application logging with JSON format"""
    
    # Create logger
    logger = logging.getLogger("aurora_assess")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Set JSON formatter
    json_formatter = JSONFormatter()
    console_handler.setFormatter(json_formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


# Global logger instance
logger = setup_logging()


def log_api_request(
    method: str,
    path: str,
    user_id: str = None,
    status_code: int = None,
    duration_ms: float = None
):
    """Log API request with structured data"""
    logger.info(
        "API Request",
        extra={
            "event_type": "api_request",
            "method": method,
            "path": path,
            "user_id": user_id,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
    )


def log_agent_execution(
    agent_type: str,
    task_id: str,
    status: str,
    input_data: Dict = None,
    output_data: Dict = None,
    duration_ms: float = None,
    error: str = None
):
    """Log agent execution with structured data"""
    logger.info(
        f"Agent Execution: {agent_type}",
        extra={
            "event_type": "agent_execution",
            "agent_type": agent_type,
            "task_id": task_id,
            "status": status,
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms,
            "error": error,
        }
    )


def log_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: float,
    success: bool = True,
    error: str = None
):
    """Log LLM API call with structured data"""
    logger.info(
        f"LLM Call: {model}",
        extra={
            "event_type": "llm_call",
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        }
    )
