"""
Property-Based Tests for LLM Integration

Tests universal properties that should hold for all LLM interactions.
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, AsyncMock, patch
import json
import time
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm.client import LLMClient, LLMConfig, LLMProvider, LLMResponse
from llm.prompts import PromptTemplate, PromptRegistry
from llm.parser import ResponseParser
from llm.rate_limiter import RateLimiter


# Property 67: LLM Call Logging
@pytest.mark.asyncio
@settings(max_examples=50, deadline=None)
@given(
    prompt=st.text(min_size=1, max_size=500),
    system_prompt=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    temperature=st.floats(min_value=0.0, max_value=2.0),
    max_tokens=st.integers(min_value=10, max_value=2000)
)
async def test_property_67_llm_call_logging(prompt, system_prompt, temperature, max_tokens):
    """
    Feature: aurora-assess, Property 67: LLM Call Logging
    
    For any LLM API call, a log entry should be created with prompt, response,
    token count, and latency.
    
    Validates: Requirements 15.3
    """
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage.total_tokens = 50
    mock_response.model_dump.return_value = {}
    
    # Track log calls
    log_calls = []
    
    def mock_log_info(msg, extra=None):
        log_calls.append({"message": msg, "extra": extra})
    
    with patch('backend.llm.client.AsyncOpenAI') as mock_openai, \
         patch('backend.llm.client.AsyncAnthropic'), \
         patch('backend.llm.client.logger') as mock_logger:
        
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client
        
        mock_logger.info = mock_log_info
        mock_logger.debug = lambda *args, **kwargs: None
        mock_logger.warning = lambda *args, **kwargs: None
        
        config = LLMConfig(
            temperature=temperature,
            max_tokens=max_tokens
        )
        client = LLMClient(config)
        client.rate_limiter = Mock()
        client.rate_limiter.acquire = AsyncMock()
        
        # Make LLM call
        response = await client.complete(
            prompt=prompt,
            system_prompt=system_prompt
        )
        
        # Verify log entry was created
        llm_logs = [log for log in log_calls if log.get("extra", {}).get("event") == "llm_completion"]
        assert len(llm_logs) > 0, "No LLM completion log entry found"
        
        log_entry = llm_logs[0]["extra"]
        
        # Verify required fields in log entry
        assert "provider" in log_entry, "Log missing provider"
        assert "model" in log_entry, "Log missing model"
        assert "tokens_used" in log_entry, "Log missing tokens_used"
        assert "latency_ms" in log_entry, "Log missing latency_ms"
        assert "finish_reason" in log_entry, "Log missing finish_reason"
        assert "prompt_length" in log_entry, "Log missing prompt_length"
        assert "response_length" in log_entry, "Log missing response_length"
        
        # Verify log data is accurate
        assert log_entry["tokens_used"] == 50
        assert log_entry["prompt_length"] == len(prompt)
        assert log_entry["response_length"] == len("Test response")
        
        if system_prompt:
            assert "system_prompt_length" in log_entry, "Log missing system_prompt_length when system prompt provided"


# Additional property: Token counting consistency
@settings(max_examples=50)
@given(text=st.text(min_size=0, max_size=1000))
def test_property_token_counting_consistency(text):
    """
    Property: Token counting should be consistent for the same text
    
    For any text, counting tokens multiple times should return the same result.
    """
    with patch('backend.llm.client.AsyncOpenAI'), \
         patch('backend.llm.client.AsyncAnthropic'):
        client = LLMClient()
        
        count1 = client.count_tokens(text)
        count2 = client.count_tokens(text)
        
        assert count1 == count2, "Token counting is not consistent"
        assert count1 >= 0, "Token count should be non-negative"


# Property: Prompt template rendering is deterministic
@settings(max_examples=50)
@given(
    name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
    age=st.integers(min_value=0, max_value=150)
)
def test_property_prompt_rendering_deterministic(name, age):
    """
    Property: Prompt template rendering should be deterministic
    
    For any template and variables, rendering multiple times should produce
    the same result.
    """
    template = PromptTemplate(
        name="test",
        template="Name: ${name}, Age: ${age}",
        required_vars=["name", "age"]
    )
    
    result1 = template.render(name=name, age=age)
    result2 = template.render(name=name, age=age)
    
    assert result1 == result2, "Template rendering is not deterministic"
    assert str(name) in result1, "Name not in rendered template"
    assert str(age) in result1, "Age not in rendered template"


# Property: JSON extraction is idempotent
@settings(max_examples=50)
@given(
    data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
        values=st.one_of(
            st.text(max_size=50),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans()
        ),
        min_size=1,
        max_size=10
    )
)
def test_property_json_extraction_idempotent(data):
    """
    Property: JSON extraction should be idempotent
    
    For any valid JSON, extracting it multiple times should produce the same result.
    """
    json_text = json.dumps(data)
    
    result1 = ResponseParser.extract_json(json_text)
    result2 = ResponseParser.extract_json(json_text)
    
    assert result1 == result2, "JSON extraction is not idempotent"
    assert result1 == data, "Extracted JSON doesn't match original data"


# Property: Rate limiter never allows negative capacity
@pytest.mark.asyncio
@settings(max_examples=30, deadline=None)
@given(
    requests=st.integers(min_value=1, max_value=10),
    tokens_per_request=st.integers(min_value=1, max_value=1000)
)
async def test_property_rate_limiter_non_negative_capacity(requests, tokens_per_request):
    """
    Property: Rate limiter should never have negative available capacity
    
    For any sequence of requests, available capacity should always be >= 0.
    """
    limiter = RateLimiter(
        requests_per_minute=100,
        tokens_per_minute=100000
    )
    
    for _ in range(requests):
        await limiter.acquire(tokens=tokens_per_request)
        
        stats = await limiter.get_stats()
        
        assert stats["available_requests"] >= 0, "Negative request capacity"
        assert stats["available_tokens"] >= 0, "Negative token capacity"


# Property: Cosine similarity is symmetric
@settings(max_examples=50)
@given(
    vec1=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3),
    vec2=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3)
)
def test_property_cosine_similarity_symmetric(vec1, vec2):
    """
    Property: Cosine similarity should be symmetric
    
    For any two vectors, similarity(A, B) should equal similarity(B, A).
    """
    with patch('backend.llm.embeddings.AsyncOpenAI'):
        from backend.llm.embeddings import EmbeddingGenerator
        
        generator = EmbeddingGenerator()
        
        sim1 = generator.cosine_similarity(vec1, vec2)
        sim2 = generator.cosine_similarity(vec2, vec1)
        
        assert abs(sim1 - sim2) < 0.0001, "Cosine similarity is not symmetric"


# Property: Cosine similarity bounds
@settings(max_examples=50)
@given(
    vec1=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3),
    vec2=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3)
)
def test_property_cosine_similarity_bounds(vec1, vec2):
    """
    Property: Cosine similarity should be between -1 and 1
    
    For any two vectors, their cosine similarity should be in [-1, 1].
    """
    with patch('backend.llm.embeddings.AsyncOpenAI'):
        from backend.llm.embeddings import EmbeddingGenerator
        
        generator = EmbeddingGenerator()
        
        similarity = generator.cosine_similarity(vec1, vec2)
        
        assert -1.0 <= similarity <= 1.0, f"Cosine similarity {similarity} out of bounds"


# Property: List parsing always returns a list
@settings(max_examples=50)
@given(text=st.text(min_size=1, max_size=500))
def test_property_list_parsing_returns_list(text):
    """
    Property: List parsing should always return a list
    
    For any text input, parse_list_response should return a list (possibly with one item).
    """
    result = ResponseParser.parse_list_response(text)
    
    assert isinstance(result, list), "Result is not a list"
    assert len(result) > 0, "Result list is empty"
    assert all(isinstance(item, str) for item in result), "Not all items are strings"


# Property: Text cleaning is idempotent
@settings(max_examples=50)
@given(text=st.text(min_size=1, max_size=500))
def test_property_text_cleaning_idempotent(text):
    """
    Property: Text cleaning should be idempotent
    
    For any text, cleaning it multiple times should produce the same result.
    """
    cleaned1 = ResponseParser.clean_text(text)
    cleaned2 = ResponseParser.clean_text(cleaned1)
    
    assert cleaned1 == cleaned2, "Text cleaning is not idempotent"


# Property: Required field validation is consistent
@settings(max_examples=50)
@given(
    data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))),
        values=st.text(max_size=50),
        min_size=1,
        max_size=10
    )
)
def test_property_required_field_validation_consistent(data):
    """
    Property: Required field validation should be consistent
    
    For any data and required fields, validation should give the same result
    when called multiple times.
    """
    required_fields = list(data.keys())[:len(data) // 2] if len(data) > 1 else list(data.keys())
    
    result1 = ResponseParser.validate_required_fields(data, required_fields)
    result2 = ResponseParser.validate_required_fields(data, required_fields)
    
    assert result1 == result2, "Field validation is not consistent"
    assert result1 is True, "Validation should pass when all required fields present"
