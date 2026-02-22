"""
Unit Tests for LLM Integration Layer

Tests the LLM client, prompt templates, response parsing, and embeddings.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm.client import LLMClient, LLMConfig, LLMProvider, LLMResponse
from llm.prompts import PromptTemplate, PromptRegistry, PromptType
from llm.parser import ResponseParser
from llm.embeddings import EmbeddingGenerator
from llm.rate_limiter import RateLimiter


class TestPromptTemplate:
    """Test prompt template functionality"""

    def test_template_creation(self):
        """Test creating a prompt template"""
        template = PromptTemplate(
            name="test_template",
            template="Hello ${name}, you are ${age} years old.",
            required_vars=["name", "age"],
            description="Test template"
        )
        
        assert template.name == "test_template"
        assert template.required_vars == ["name", "age"]

    def test_template_rendering(self):
        """Test rendering a template with variables"""
        template = PromptTemplate(
            name="test",
            template="Hello ${name}!",
            required_vars=["name"]
        )
        
        rendered = template.render(name="Alice")
        assert rendered == "Hello Alice!"

    def test_template_missing_required_var(self):
        """Test that missing required variables raise an error"""
        template = PromptTemplate(
            name="test",
            template="Hello ${name}!",
            required_vars=["name"]
        )
        
        with pytest.raises(ValueError, match="Missing required variables"):
            template.render()

    def test_template_with_system_prompt(self):
        """Test template with system prompt"""
        template = PromptTemplate(
            name="test",
            template="User prompt",
            system_prompt="System instructions"
        )
        
        assert template.get_system_prompt() == "System instructions"


class TestPromptRegistry:
    """Test prompt registry functionality"""

    def test_registry_initialization(self):
        """Test that registry initializes with default templates"""
        registry = PromptRegistry()
        
        templates = registry.list_templates()
        assert len(templates) > 0
        assert PromptType.QUESTION_TAGGING in templates

    def test_register_template(self):
        """Test registering a new template"""
        registry = PromptRegistry()
        
        template = PromptTemplate(
            name="custom_template",
            template="Custom ${var}"
        )
        
        registry.register(template)
        assert "custom_template" in registry.list_templates()

    def test_get_template(self):
        """Test retrieving a template"""
        registry = PromptRegistry()
        
        template = registry.get(PromptType.QUESTION_TAGGING)
        assert template is not None
        assert template.name == PromptType.QUESTION_TAGGING

    def test_get_nonexistent_template(self):
        """Test that getting nonexistent template raises error"""
        registry = PromptRegistry()
        
        with pytest.raises(KeyError):
            registry.get("nonexistent_template")

    def test_render_template(self):
        """Test rendering through registry"""
        registry = PromptRegistry()
        
        rendered, system_prompt = registry.render(
            PromptType.QUESTION_TAGGING,
            question_text="What is 2+2?"
        )
        
        assert "What is 2+2?" in rendered
        assert system_prompt is not None


class TestResponseParser:
    """Test response parser functionality"""

    def test_extract_json_direct(self):
        """Test extracting JSON from direct JSON string"""
        text = '{"key": "value", "number": 42}'
        result = ResponseParser.extract_json(text)
        
        assert result == {"key": "value", "number": 42}

    def test_extract_json_from_markdown(self):
        """Test extracting JSON from markdown code block"""
        text = """
        Here is the result:
        ```json
        {"key": "value"}
        ```
        """
        result = ResponseParser.extract_json(text)
        
        assert result == {"key": "value"}

    def test_extract_json_embedded(self):
        """Test extracting JSON embedded in text"""
        text = "The answer is: {\"result\": 42} as you can see."
        result = ResponseParser.extract_json(text)
        
        assert result == {"result": 42}

    def test_extract_json_none(self):
        """Test that invalid JSON returns None"""
        text = "This is just plain text with no JSON"
        result = ResponseParser.extract_json(text)
        
        assert result is None

    def test_clean_text(self):
        """Test text cleaning"""
        text = "  Hello   world  \n\n  with   spaces  "
        cleaned = ResponseParser.clean_text(text)
        
        assert cleaned == "Hello world with spaces"

    def test_extract_code_blocks(self):
        """Test extracting code blocks"""
        text = """
        ```python
        print("hello")
        ```
        Some text
        ```javascript
        console.log("world")
        ```
        """
        
        blocks = ResponseParser.extract_code_blocks(text)
        assert len(blocks) == 2
        assert 'print("hello")' in blocks[0]
        
        python_blocks = ResponseParser.extract_code_blocks(text, language="python")
        assert len(python_blocks) == 1

    def test_validate_required_fields(self):
        """Test required field validation"""
        data = {"name": "Alice", "age": 30}
        
        assert ResponseParser.validate_required_fields(data, ["name", "age"])
        assert not ResponseParser.validate_required_fields(data, ["name", "email"])

    def test_parse_list_response_json(self):
        """Test parsing list from JSON array"""
        text = '["item1", "item2", "item3"]'
        result = ResponseParser.parse_list_response(text)
        
        assert result == ["item1", "item2", "item3"]

    def test_parse_list_response_numbered(self):
        """Test parsing numbered list"""
        text = """
        1. First item
        2. Second item
        3. Third item
        """
        result = ResponseParser.parse_list_response(text)
        
        assert len(result) == 3
        assert "First item" in result

    def test_parse_list_response_bullets(self):
        """Test parsing bullet list"""
        text = """
        - First item
        - Second item
        - Third item
        """
        result = ResponseParser.parse_list_response(text)
        
        assert len(result) == 3


class TestRateLimiter:
    """Test rate limiter functionality"""

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test rate limiter initialization"""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=90000
        )
        
        assert limiter.requests_per_minute == 60
        assert limiter.tokens_per_minute == 90000

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring when within rate limit"""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=90000
        )
        
        # Should not block
        await limiter.acquire(tokens=100)
        
        stats = await limiter.get_stats()
        assert stats["available_requests"] < limiter.max_requests

    @pytest.mark.asyncio
    async def test_rate_limiter_refill(self):
        """Test that rate limiter refills over time"""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=90000
        )
        
        # Consume some capacity
        await limiter.acquire(tokens=1000)
        
        stats_before = await limiter.get_stats()
        
        # Wait for refill
        await asyncio.sleep(0.2)
        
        stats_after = await limiter.get_stats()
        
        # Should have refilled
        assert stats_after["available_tokens"] > stats_before["available_tokens"]

    @pytest.mark.asyncio
    async def test_rate_limiter_reset(self):
        """Test resetting rate limiter"""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=90000
        )
        
        # Consume capacity
        await limiter.acquire(tokens=1000)
        
        # Reset
        limiter.reset()
        
        stats = await limiter.get_stats()
        assert stats["available_requests"] == limiter.max_requests
        assert stats["available_tokens"] == limiter.max_tokens


@pytest.mark.asyncio
class TestLLMClient:
    """Test LLM client functionality"""

    async def test_client_initialization(self):
        """Test LLM client initialization"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4"
        )
        
        with patch('backend.llm.client.AsyncOpenAI'), \
             patch('backend.llm.client.AsyncAnthropic'):
            client = LLMClient(config)
            
            assert client.config.provider == LLMProvider.OPENAI
            assert client.config.model == "gpt-4"

    async def test_token_counting(self):
        """Test token counting"""
        with patch('backend.llm.client.AsyncOpenAI'), \
             patch('backend.llm.client.AsyncAnthropic'):
            client = LLMClient()
            
            text = "Hello world"
            tokens = client.count_tokens(text)
            
            assert tokens > 0
            assert isinstance(tokens, int)

    async def test_complete_openai_success(self):
        """Test successful OpenAI completion"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.total_tokens = 50
        mock_response.model_dump.return_value = {}
        
        with patch('backend.llm.client.AsyncOpenAI') as mock_openai, \
             patch('backend.llm.client.AsyncAnthropic'):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            client = LLMClient()
            client.rate_limiter = Mock()
            client.rate_limiter.acquire = AsyncMock()
            
            response = await client.complete("Test prompt")
            
            assert response.content == "Test response"
            assert response.provider == LLMProvider.OPENAI
            assert response.tokens_used == 50

    async def test_complete_with_retry(self):
        """Test completion with retry on failure"""
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.total_tokens = 50
        mock_response.model_dump.return_value = {}
        
        with patch('backend.llm.client.AsyncOpenAI') as mock_openai, \
             patch('backend.llm.client.AsyncAnthropic'):
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=[Exception("API Error"), mock_response]
            )
            mock_openai.return_value = mock_client
            
            config = LLMConfig(max_retries=2, retry_delay=0.01)
            client = LLMClient(config)
            client.rate_limiter = Mock()
            client.rate_limiter.acquire = AsyncMock()
            
            response = await client.complete("Test prompt")
            
            assert response.content == "Success"


@pytest.mark.asyncio
class TestEmbeddingGenerator:
    """Test embedding generator functionality"""

    async def test_generator_initialization(self):
        """Test embedding generator initialization"""
        with patch('backend.llm.embeddings.AsyncOpenAI'):
            generator = EmbeddingGenerator(
                model="text-embedding-3-small",
                dimensions=1536
            )
            
            assert generator.model == "text-embedding-3-small"
            assert generator.dimensions == 1536

    async def test_generate_single_embedding(self):
        """Test generating a single embedding"""
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.usage.total_tokens = 10
        
        with patch('backend.llm.embeddings.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            generator = EmbeddingGenerator()
            generator.rate_limiter = Mock()
            generator.rate_limiter.acquire = AsyncMock()
            
            embedding = await generator.generate("Test text")
            
            assert embedding == [0.1, 0.2, 0.3]

    async def test_generate_batch_embeddings(self):
        """Test generating batch of embeddings"""
        mock_response = Mock()
        mock_response.data = [Mock(), Mock()]
        mock_response.data[0].embedding = [0.1, 0.2]
        mock_response.data[1].embedding = [0.3, 0.4]
        mock_response.usage.total_tokens = 20
        
        with patch('backend.llm.embeddings.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            generator = EmbeddingGenerator()
            generator.rate_limiter = Mock()
            generator.rate_limiter.acquire = AsyncMock()
            
            embeddings = await generator.generate_batch(["Text 1", "Text 2"])
            
            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2]
            assert embeddings[1] == [0.3, 0.4]

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        with patch('backend.llm.embeddings.AsyncOpenAI'):
            generator = EmbeddingGenerator()
            
            # Identical vectors should have similarity 1.0
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [1.0, 0.0, 0.0]
            similarity = generator.cosine_similarity(vec1, vec2)
            assert abs(similarity - 1.0) < 0.001
            
            # Orthogonal vectors should have similarity 0.0
            vec3 = [1.0, 0.0, 0.0]
            vec4 = [0.0, 1.0, 0.0]
            similarity = generator.cosine_similarity(vec3, vec4)
            assert abs(similarity) < 0.001

    async def test_find_most_similar(self):
        """Test finding most similar embeddings"""
        with patch('backend.llm.embeddings.AsyncOpenAI'):
            generator = EmbeddingGenerator()
            
            query = [1.0, 0.0, 0.0]
            candidates = [
                [1.0, 0.0, 0.0],  # Identical
                [0.9, 0.1, 0.0],  # Very similar
                [0.0, 1.0, 0.0],  # Orthogonal
            ]
            
            results = await generator.find_most_similar(query, candidates, top_k=2)
            
            assert len(results) == 2
            assert results[0][0] == 0  # First candidate is most similar
            assert results[0][1] > results[1][1]  # Scores are descending
