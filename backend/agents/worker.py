"""
Agent Worker Process

This script runs the agent orchestrator as a separate process.
It should be run alongside the FastAPI application to process queued tasks.

Usage:
    python -m agents.worker
"""

import asyncio
import signal
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.orchestrator import orchestrator
from agents.ingestion_agent import IngestionAgent
from agents.pattern_miner_agent import PatternMinerAgent
from agents.question_selector_agent import QuestionSelectorAgent
from agents.answer_key_generator_agent import AnswerKeyGeneratorAgent
from agents.grading_evaluator_agent import GradingEvaluatorAgent
from agents.weakness_analyzer_agent import WeaknessAnalyzerAgent
from agents.roadmap_agent import RoadmapAgent
from config import settings
from utils.logger import logger


def create_sync_db_session():
    """Create synchronous database session for agents"""
    # Convert async URL to sync URL
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    
    engine = create_engine(
        sync_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
    )
    
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    
    return SessionLocal()


async def main():
    """Main worker function"""
    logger.info("Starting AURORA Assess Agent Worker...")
    
    # Initialize Redis connection
    from utils.redis_client import redis_client
    await redis_client.connect()
    logger.info("Redis connection established")
    
    # Create database session
    db = create_sync_db_session()
    logger.info("Database session created")
    
    # Register all agents
    orchestrator.register_agent(IngestionAgent(db))
    orchestrator.register_agent(PatternMinerAgent(db))
    orchestrator.register_agent(QuestionSelectorAgent(db))
    orchestrator.register_agent(AnswerKeyGeneratorAgent(db))
    orchestrator.register_agent(GradingEvaluatorAgent(db))
    orchestrator.register_agent(WeaknessAnalyzerAgent(db))
    orchestrator.register_agent(RoadmapAgent(db))
    logger.info(f"Registered {len(orchestrator.agents)} agents")
    
    # Start orchestrator
    await orchestrator.start()
    logger.info("Agent orchestrator started and processing tasks...")
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep running
    try:
        while orchestrator.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    
    await shutdown()


async def shutdown():
    """Graceful shutdown"""
    logger.info("Shutting down agent worker...")
    await orchestrator.stop()
    
    # Disconnect Redis
    from utils.redis_client import redis_client
    await redis_client.disconnect()
    logger.info("Redis connection closed")
    
    logger.info("Agent worker stopped")
    sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
    except Exception as e:
        logger.error(f"Worker error: {str(e)}")
        sys.exit(1)
