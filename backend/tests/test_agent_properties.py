"""
Property-based tests for agent orchestration system.

Tests cover:
- Property 61: Event publishing correctness
- Property 62: Exponential backoff behavior
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings
from hypothesis import assume
import time

from agents.events import event_bus
from agents.retry import calculate_backoff, RetryPolicy


@pytest.mark.property
class TestEventPublishingProperties:
    """Property tests for event publishing (Property 61)"""
    
    @pytest.mark.asyncio
    @given(
        event_type=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='._-'
        )),
        data_keys=st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd')
            )),
            min_size=1,
            max_size=10,
            unique=True
        ),
        data_values=st.lists(
            st.one_of(
                st.text(max_size=100),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans()
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50, deadline=5000)
    async def test_event_publishing_returns_subscriber_count(
        self,
        event_type: str,
        data_keys: list,
        data_values: list
    ):
        """
        Property 61: Event publishing returns number of subscribers.
        
        For any event type and data, publishing should return a non-negative
        integer representing the number of subscribers that received the event.
        """
        # Ensure keys and values have same length
        assume(len(data_keys) == len(data_values))
        
        # Create data dictionary
        data = dict(zip(data_keys, data_values))
        
        # Publish event
        num_subscribers = await event_bus.publish(event_type, data)
        
        # Property: Result should be a non-negative integer
        assert isinstance(num_subscribers, int)
        assert num_subscribers >= 0
    
    @pytest.mark.asyncio
    @given(
        event_type=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='._-'
        )),
        num_subscribers=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=30, deadline=5000)
    async def test_event_received_by_all_subscribers(
        self,
        event_type: str,
        num_subscribers: int
    ):
        """
        Property 61: All subscribers receive published events.
        
        If N callbacks are subscribed to an event type, all N should
        be called when an event is published.
        """
        received_count = [0]  # Use list to allow modification in callback
        
        def callback(event):
            received_count[0] += 1
        
        # Subscribe multiple callbacks
        for _ in range(num_subscribers):
            event_bus.subscribe(event_type, callback)
        
        try:
            # Publish event
            await event_bus.publish(event_type, {"test": "data"})
            
            # Small delay for async processing
            await asyncio.sleep(0.1)
            
            # Property: All subscribers should receive the event
            assert received_count[0] == num_subscribers
            
        finally:
            # Cleanup: unsubscribe all
            for _ in range(num_subscribers):
                event_bus.unsubscribe(event_type, callback)
    
    @pytest.mark.asyncio
    @given(
        event_type=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='._-'
        )),
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50, deadline=5000)
    async def test_event_data_preserved(self, event_type: str, data: dict):
        """
        Property 61: Event data is preserved during publishing.
        
        The data published should match the data received by subscribers.
        """
        received_data = [None]
        
        def callback(event):
            received_data[0] = event.get("data")
        
        event_bus.subscribe(event_type, callback)
        
        try:
            # Publish event
            await event_bus.publish(event_type, data)
            
            # Small delay for async processing
            await asyncio.sleep(0.1)
            
            # Property: Received data should match published data
            assert received_data[0] == data
            
        finally:
            event_bus.unsubscribe(event_type, callback)
    
    @pytest.mark.asyncio
    @given(
        event_type=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='._-'
        ))
    )
    @settings(max_examples=30, deadline=5000)
    async def test_event_has_timestamp(self, event_type: str):
        """
        Property 61: Published events include timestamp.
        
        Every published event should have a timestamp field.
        """
        received_event = [None]
        
        def callback(event):
            received_event[0] = event
        
        event_bus.subscribe(event_type, callback)
        
        try:
            # Publish event
            await event_bus.publish(event_type, {"test": "data"})
            
            # Small delay for async processing
            await asyncio.sleep(0.1)
            
            # Property: Event should have timestamp
            assert received_event[0] is not None
            assert "timestamp" in received_event[0]
            assert isinstance(received_event[0]["timestamp"], str)
            
        finally:
            event_bus.unsubscribe(event_type, callback)


@pytest.mark.property
class TestExponentialBackoffProperties:
    """Property tests for exponential backoff (Property 62)"""
    
    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        max_delay=st.floats(min_value=1.0, max_value=300.0)
    )
    @settings(max_examples=100)
    def test_backoff_increases_with_attempts(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float
    ):
        """
        Property 62: Backoff delay increases with attempt number.
        
        For any attempt N, the delay should be greater than or equal to
        the delay for attempt N-1 (up to max_delay).
        """
        assume(max_delay >= base_delay)
        
        if attempt == 0:
            # First attempt, just check it's valid
            delay = calculate_backoff(
                attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=False
            )
            assert delay >= base_delay
        else:
            # Compare with previous attempt
            prev_delay = calculate_backoff(
                attempt - 1,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=False
            )
            curr_delay = calculate_backoff(
                attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=False
            )
            
            # Property: Current delay >= previous delay (or both at max)
            assert curr_delay >= prev_delay or curr_delay == max_delay
    
    @given(
        attempt=st.integers(min_value=0, max_value=20),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        max_delay=st.floats(min_value=1.0, max_value=300.0)
    )
    @settings(max_examples=100)
    def test_backoff_respects_max_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float
    ):
        """
        Property 62: Backoff delay never exceeds max_delay.
        
        For any attempt number, the calculated delay should never
        exceed the specified maximum delay.
        """
        assume(max_delay >= base_delay)
        
        delay = calculate_backoff(
            attempt,
            base_delay=base_delay,
            max_delay=max_delay,
            jitter=False
        )
        
        # Property: Delay should not exceed max_delay
        assert delay <= max_delay
    
    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        exponential_base=st.floats(min_value=1.5, max_value=3.0)
    )
    @settings(max_examples=100)
    def test_backoff_is_exponential(
        self,
        attempt: int,
        base_delay: float,
        exponential_base: float
    ):
        """
        Property 62: Backoff follows exponential growth.
        
        The delay should grow exponentially with the attempt number
        according to the formula: base_delay * (exponential_base ^ attempt)
        """
        delay = calculate_backoff(
            attempt,
            base_delay=base_delay,
            max_delay=1000.0,  # High max to not interfere
            exponential_base=exponential_base,
            jitter=False
        )
        
        expected_delay = base_delay * (exponential_base ** attempt)
        
        # Property: Delay should match exponential formula
        # (within floating point tolerance)
        assert abs(delay - expected_delay) < 0.01
    
    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0)
    )
    @settings(max_examples=100)
    def test_backoff_with_jitter_is_random(
        self,
        attempt: int,
        base_delay: float
    ):
        """
        Property 62: Jitter adds randomness to backoff.
        
        With jitter enabled, multiple calculations for the same attempt
        should produce different results (with high probability).
        """
        delays = set()
        
        # Calculate delay multiple times
        for _ in range(10):
            delay = calculate_backoff(
                attempt,
                base_delay=base_delay,
                max_delay=1000.0,
                jitter=True
            )
            delays.add(delay)
        
        # Property: Should have multiple different values (randomness)
        # At least 5 different values out of 10 attempts
        assert len(delays) >= 5
    
    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0),
        max_delay=st.floats(min_value=1.0, max_value=300.0)
    )
    @settings(max_examples=100)
    def test_backoff_with_jitter_respects_bounds(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float
    ):
        """
        Property 62: Jitter keeps delay within reasonable bounds.
        
        Even with jitter, the delay should be between 50% and 100%
        of the non-jittered delay (and still respect max_delay).
        """
        assume(max_delay >= base_delay)
        
        # Calculate non-jittered delay
        base_calc = calculate_backoff(
            attempt,
            base_delay=base_delay,
            max_delay=max_delay,
            jitter=False
        )
        
        # Calculate jittered delay
        jittered = calculate_backoff(
            attempt,
            base_delay=base_delay,
            max_delay=max_delay,
            jitter=True
        )
        
        # Property: Jittered delay should be between 50% and 100% of base
        # (or at max_delay)
        assert jittered >= base_calc * 0.5
        assert jittered <= max_delay
    
    @pytest.mark.asyncio
    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        base_delay=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=20, deadline=10000)
    async def test_retry_policy_respects_max_retries(
        self,
        max_retries: int,
        base_delay: float
    ):
        """
        Property 62: Retry policy respects maximum retry count.
        
        A retry policy should not retry more than max_retries times.
        """
        policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=60.0
        )
        
        attempt_count = [0]
        
        async def failing_function():
            attempt_count[0] += 1
            raise Exception("Test failure")
        
        # Try to execute with retries
        with pytest.raises(Exception):
            await policy.execute_with_retry(failing_function)
        
        # Property: Should attempt exactly max_retries + 1 times
        # (initial attempt + retries)
        assert attempt_count[0] == max_retries + 1
    
    @pytest.mark.asyncio
    @given(
        base_delay=st.floats(min_value=0.01, max_value=0.1)
    )
    @settings(max_examples=10, deadline=5000)
    async def test_retry_policy_delays_between_attempts(
        self,
        base_delay: float
    ):
        """
        Property 62: Retry policy adds delay between attempts.
        
        There should be a measurable delay between retry attempts.
        """
        policy = RetryPolicy(
            max_retries=2,
            base_delay=base_delay,
            max_delay=1.0,
            jitter=False
        )
        
        attempt_times = []
        
        async def failing_function():
            attempt_times.append(time.time())
            raise Exception("Test failure")
        
        # Try to execute with retries
        with pytest.raises(Exception):
            await policy.execute_with_retry(failing_function)
        
        # Property: Should have delays between attempts
        if len(attempt_times) >= 2:
            for i in range(1, len(attempt_times)):
                time_diff = attempt_times[i] - attempt_times[i-1]
                # Should have at least some delay (accounting for execution time)
                assert time_diff >= base_delay * 0.5
