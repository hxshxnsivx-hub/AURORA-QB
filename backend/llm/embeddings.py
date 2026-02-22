"""
Embedding Generation

Generates vector embeddings for semantic search using OpenAI's embedding models.
"""

import asyncio
from typing import List, Optional
import numpy as np

from openai import AsyncOpenAI

from config import settings
from utils.logger import get_logger
from llm.rate_limiter import RateLimiter

logger = get_logger(__name__)


class EmbeddingGenerator:
    """
    Generates vector embeddings for text using OpenAI's embedding models
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 100
    ):
        """
        Initialize embedding generator
        
        Args:
            model: OpenAI embedding model name
            dimensions: Embedding dimension size
            batch_size: Maximum texts to embed in one API call
        """
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60
        )
        
        # Rate limiter for embedding API
        # Embedding API has different limits than completion API
        self.rate_limiter = RateLimiter(
            requests_per_minute=3000,
            tokens_per_minute=1000000
        )
        
        logger.info(
            "Embedding generator initialized",
            extra={
                "model": model,
                "dimensions": dimensions,
                "batch_size": batch_size
            }
        )

    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.generate_batch([text])
        return embeddings[0]

    async def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Process in batches
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self._generate_batch_internal(batch)
            all_embeddings.extend(batch_embeddings)
        
        logger.info(
            f"Generated embeddings for {len(texts)} texts",
            extra={"text_count": len(texts), "batch_count": (len(texts) + self.batch_size - 1) // self.batch_size}
        )
        
        return all_embeddings

    async def _generate_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """
        Internal method to generate embeddings for a batch
        
        Args:
            texts: Batch of texts (up to batch_size)
            
        Returns:
            List of embedding vectors
        """
        # Estimate tokens for rate limiting
        total_tokens = sum(len(text.split()) * 1.3 for text in texts)  # Rough estimate
        
        # Wait for rate limit
        await self.rate_limiter.acquire(tokens=int(total_tokens))
        
        try:
            # Call OpenAI API
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            
            logger.debug(
                f"Generated batch of {len(texts)} embeddings",
                extra={
                    "batch_size": len(texts),
                    "tokens_used": response.usage.total_tokens,
                    "model": self.model
                }
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}", extra={"error": str(e)})
            raise

    async def generate_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> List[float]:
        """
        Generate embedding with retry logic
        
        Args:
            text: Text to embed
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
            
        Returns:
            Embedding vector
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self.generate(text)
            except Exception as e:
                last_error = e
                
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Embedding generation failed (attempt {attempt + 1}/{max_retries}), retrying...",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(delay)
        
        raise last_error

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0 to 1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    async def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 10
    ) -> List[tuple[int, float]]:
        """
        Find most similar embeddings to query
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        similarities = []
        
        for idx, candidate in enumerate(candidate_embeddings):
            similarity = self.cosine_similarity(query_embedding, candidate)
            similarities.append((idx, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]

    async def close(self):
        """Close API client"""
        await self.client.close()
