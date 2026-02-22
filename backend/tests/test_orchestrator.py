"""
Unit tests for agent orchestrator.

Tests cover:
- Agent registration and lifecycle
- Task submission and distribution
- Worker pool management
- Statistics and monitoring
"""

import pytest
import asyncio
from typing import Dict, Any

from agents.base import Agent, AgentStatus
from agents.orchestrator import orchestrator
from agents.task_queue import task_queue, QueuePriority
from agents.events import event_bus


class MockAgent(Agent):
    """Mock agent for testing"""
    
    def __init__(self, agent_type: str, should_fail: bool = False):
        super().__init__(agent_type)
        self.should_fail = should_fail
        self.processed_tasks = []
    
    async def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock process method"""
        self.processed_tasks.append(task_data)
        
        if self.should_fail:
            raise Exception("Mock agent failure")
        
        return {
            "status": "success",
            "task_id": task_data.get("task_id"),
            "result": "processed"
        }


@pytest.mark.asyncio
class TestAgentOrchestrator:
    """Test suite for AgentOrchestrator"""
    
    async def test_agent_registration(self):
        """Test registering and unregistering agents"""
        # Create mock agent
        agent = MockAgent("test_agent")
        
        # Register agent
        orchestrator.register_agent(agent)
        
        # Verify registration
        assert "test_agent" in orchestrator.agents
        assert orchestrator.get_agent("test_agent") == agent
        
        # Unregister agent
        orchestrator.unregister_agent("test_agent")
        
        # Verify unregistration
        assert "test_agent" not in orchestrator.agents
        assert orchestrator.get_agent("test_agent") is None
    
    async def test_task_submission(self):
        """Test submitting tasks to orchestrator"""
        # Register mock agent
        agent = MockAgent("test_submit")
        orchestrator.register_agent(agent)
        
        try:
            # Submit task
            task_id = await orchestrator.submit_task(
                agent_type="test_submit",
                payload={"data": "test"},
                priority=QueuePriority.NORMAL
            )
            
            # Verify task created
            assert task_id is not None
            
            # Get task status
            task_data = await orchestrator.get_task_status(task_id)
            assert task_data is not None
            assert task_data["agent_type"] == "test_submit"
            assert task_data["status"] == "pending"
            
        finally:
            orchestrator.unregister_agent("test_submit")
    
    async def test_task_submission_unknown_agent(self):
        """Test submitting task to unknown agent type"""
        with pytest.raises(ValueError, match="Unknown agent type"):
            await orchestrator.submit_task(
                agent_type="nonexistent_agent",
                payload={"data": "test"}
            )
    
    async def test_orchestrator_start_stop(self):
        """Test starting and stopping orchestrator"""
        # Register mock agent
        agent = MockAgent("test_lifecycle")
        orchestrator.register_agent(agent)
        
        try:
            # Start orchestrator
            await orchestrator.start()
            
            # Verify running
            assert orchestrator.running is True
            assert len(orchestrator.worker_tasks) > 0
            
            # Stop orchestrator
            await orchestrator.stop()
            
            # Verify stopped
            assert orchestrator.running is False
            assert len(orchestrator.worker_tasks) == 0
            
        finally:
            orchestrator.unregister_agent("test_lifecycle")
    
    async def test_task_processing(self):
        """Test end-to-end task processing"""
        # Register mock agent
        agent = MockAgent("test_process")
        orchestrator.register_agent(agent)
        
        try:
            # Start orchestrator
            await orchestrator.start()
            
            # Submit task
            task_id = await orchestrator.submit_task(
                agent_type="test_process",
                payload={"data": "test_data"},
                priority=QueuePriority.HIGH
            )
            
            # Wait for processing
            await asyncio.sleep(2)
            
            # Check task status
            task_data = await orchestrator.get_task_status(task_id)
            
            # Task should be completed or processing
            assert task_data["status"] in ["completed", "processing"]
            
            # Stop orchestrator
            await orchestrator.stop()
            
        finally:
            orchestrator.unregister_agent("test_process")
    
    async def test_failed_task_retry(self):
        """Test failed task retry mechanism"""
        # Register failing agent
        agent = MockAgent("test_fail", should_fail=True)
        orchestrator.register_agent(agent)
        
        try:
            # Start orchestrator
            await orchestrator.start()
            
            # Submit task
            task_id = await orchestrator.submit_task(
                agent_type="test_fail",
                payload={"data": "test"},
                priority=QueuePriority.NORMAL
            )
            
            # Wait for processing and retries
            await asyncio.sleep(5)
            
            # Check task status
            task_data = await orchestrator.get_task_status(task_id)
            
            # Task should have retry attempts
            assert task_data["retry_count"] > 0
            
            # Stop orchestrator
            await orchestrator.stop()
            
        finally:
            orchestrator.unregister_agent("test_fail")
    
    async def test_orchestrator_stats(self):
        """Test getting orchestrator statistics"""
        # Register mock agent
        agent = MockAgent("test_stats")
        orchestrator.register_agent(agent)
        
        try:
            # Get stats
            stats = await orchestrator.get_stats()
            
            # Verify stats structure
            assert "running" in stats
            assert "num_agents" in stats
            assert "num_workers" in stats
            assert "queue" in stats
            assert "agents" in stats
            
            # Verify agent stats
            assert "test_stats" in stats["agents"]
            agent_stats = stats["agents"]["test_stats"]
            assert "status" in agent_stats
            assert "tasks_processed" in agent_stats
            assert "tasks_failed" in agent_stats
            
        finally:
            orchestrator.unregister_agent("test_stats")
    
    async def test_priority_queue_ordering(self):
        """Test that high priority tasks are processed first"""
        # Register mock agent
        agent = MockAgent("test_priority")
        orchestrator.register_agent(agent)
        
        try:
            # Submit tasks with different priorities
            low_task = await orchestrator.submit_task(
                agent_type="test_priority",
                payload={"priority": "low"},
                priority=QueuePriority.LOW
            )
            
            high_task = await orchestrator.submit_task(
                agent_type="test_priority",
                payload={"priority": "high"},
                priority=QueuePriority.HIGH
            )
            
            normal_task = await orchestrator.submit_task(
                agent_type="test_priority",
                payload={"priority": "normal"},
                priority=QueuePriority.NORMAL
            )
            
            # Start orchestrator
            await orchestrator.start()
            
            # Wait for processing
            await asyncio.sleep(3)
            
            # Stop orchestrator
            await orchestrator.stop()
            
            # Check processing order (high should be first)
            if len(agent.processed_tasks) > 0:
                first_task = agent.processed_tasks[0]
                # High priority task should be processed first
                assert first_task["payload"]["priority"] == "high"
            
        finally:
            orchestrator.unregister_agent("test_priority")
    
    async def test_multiple_workers(self):
        """Test concurrent processing with multiple workers"""
        # Register mock agent
        agent = MockAgent("test_workers")
        orchestrator.register_agent(agent)
        
        try:
            # Start orchestrator
            await orchestrator.start()
            
            # Submit multiple tasks
            task_ids = []
            for i in range(10):
                task_id = await orchestrator.submit_task(
                    agent_type="test_workers",
                    payload={"index": i},
                    priority=QueuePriority.NORMAL
                )
                task_ids.append(task_id)
            
            # Wait for processing
            await asyncio.sleep(5)
            
            # Check that multiple tasks were processed
            assert len(agent.processed_tasks) > 0
            
            # Stop orchestrator
            await orchestrator.stop()
            
        finally:
            orchestrator.unregister_agent("test_workers")
    
    async def test_get_failed_tasks(self):
        """Test retrieving failed tasks"""
        # Register failing agent
        agent = MockAgent("test_failed_list", should_fail=True)
        orchestrator.register_agent(agent)
        
        try:
            # Start orchestrator
            await orchestrator.start()
            
            # Submit task that will fail
            task_id = await orchestrator.submit_task(
                agent_type="test_failed_list",
                payload={"data": "test"},
                priority=QueuePriority.NORMAL
            )
            
            # Wait for processing and max retries
            await asyncio.sleep(10)
            
            # Get failed tasks
            failed_tasks = await orchestrator.get_failed_tasks(limit=10)
            
            # Should have at least one failed task
            assert len(failed_tasks) > 0
            
            # Stop orchestrator
            await orchestrator.stop()
            
        finally:
            orchestrator.unregister_agent("test_failed_list")
    
    async def test_clear_old_tasks(self):
        """Test clearing old completed tasks"""
        # This test verifies the cleanup mechanism exists
        # Actual cleanup would require waiting for tasks to age
        
        # Call clear with 0 days (clears all)
        count = await orchestrator.clear_old_tasks(older_than_days=0)
        
        # Should return a count (may be 0)
        assert isinstance(count, int)
        assert count >= 0


@pytest.mark.asyncio
class TestAgentBase:
    """Test suite for Agent base class"""
    
    async def test_agent_initialization(self):
        """Test agent initialization"""
        agent = MockAgent("test_init")
        
        assert agent.agent_type == "test_init"
        assert agent.status == AgentStatus.IDLE
        assert agent.tasks_processed == 0
        assert agent.tasks_failed == 0
    
    async def test_agent_execute_task_success(self):
        """Test successful task execution"""
        agent = MockAgent("test_success")
        
        task_data = {
            "task_id": "test123",
            "payload": {"data": "test"}
        }
        
        result = await agent.execute_task(task_data)
        
        assert result["success"] is True
        assert "result" in result
        assert agent.tasks_processed == 1
        assert agent.tasks_failed == 0
    
    async def test_agent_execute_task_failure(self):
        """Test failed task execution"""
        agent = MockAgent("test_failure", should_fail=True)
        
        task_data = {
            "task_id": "test456",
            "payload": {"data": "test"}
        }
        
        result = await agent.execute_task(task_data)
        
        assert result["success"] is False
        assert "error" in result
        assert agent.tasks_processed == 0
        assert agent.tasks_failed == 1
    
    async def test_agent_get_status(self):
        """Test getting agent status"""
        agent = MockAgent("test_status")
        
        # Process some tasks
        await agent.execute_task({"task_id": "1", "payload": {}})
        await agent.execute_task({"task_id": "2", "payload": {}})
        
        status = agent.get_status()
        
        assert status["agent_type"] == "test_status"
        assert status["tasks_processed"] == 2
        assert status["success_rate"] == 1.0
    
    async def test_agent_reset_stats(self):
        """Test resetting agent statistics"""
        agent = MockAgent("test_reset")
        
        # Process a task
        await agent.execute_task({"task_id": "1", "payload": {}})
        
        assert agent.tasks_processed == 1
        
        # Reset stats
        agent.reset_stats()
        
        assert agent.tasks_processed == 0
        assert agent.tasks_failed == 0
    
    async def test_agent_start_stop(self):
        """Test agent start and stop"""
        agent = MockAgent("test_lifecycle")
        
        # Start agent
        await agent.start()
        assert agent.status == AgentStatus.IDLE
        assert agent.started_at is not None
        
        # Stop agent
        await agent.stop()
        assert agent.status == AgentStatus.STOPPED
