#!/usr/bin/env python3
"""
Perplexity API Wrapper - Direct API integration for grounded web search

Bypasses LiteLLM to directly call Perplexity API for web search with citations.

Perplexity API: https://docs.perplexity.ai/docs/getting-started/overview
Models: sonar-small-online, sonar-medium-online
"""

import os
import json
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Security: identifier replacer for sanitization
try:
    from lib import PathResolver
    PATH_RESOLVER = PathResolver()
except ImportError:
    PATH_RESOLVER = None


@dataclass
class SearchResult:
    """A single search result from Perplexity."""
    title: str
    url: str
    snippet: str
    score: float
    source: str


@dataclass
class PerplexityResponse:
    """Complete Perplexity API response."""
    answer: str
    citations: List[SearchResult]
    model: str
    tokens_used: int
    cost: float
    latency_seconds: float


class PerplexityAPIError(Exception):
    """Custom exception for Perplexity API errors."""
    pass


class PerplexityWrapper:
    """
    Direct API wrapper for Perplexity web search.

    Provides grounded web search with citations for the Council system.
    """

    API_BASE = "https://api.perplexity.ai"

    # Perplexity models (sonar-online = search + answer)
    MODELS = {
        "sonar-small-online": {
            "model": "sonar-small-online",
            "cost_per_search": 0.001,  # ~$0.001 per search
            "max_tokens": 12000,
        },
        "sonar-medium-online": {
            "model": "sonar-medium-online",
            "cost_per_search": 0.002,  # ~$0.002 per search
            "max_tokens": 12000,
        },
    }

    DEFAULT_MODEL = "sonar-medium-online"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Perplexity wrapper.

        Args:
            api_key: Perplexity API key (defaults to PERPLEXITY_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise PerplexityAPIError(
                "PERPLEXITY_API_KEY not found. "
                "Set environment variable or pass api_key parameter."
            )

    def sanitize_query(self, query: str) -> tuple[str, Dict[str, str]]:
        """
        Sanitize query for external API calls.

        Removes internal identifiers and sensitive paths before sending to Perplexity.

        Args:
            query: The user's query

        Returns:
            Tuple of (sanitized_query, replacement_map)
        """
        # Placeholder for sanitization - would use identifier_replacer.py
        # For now, just return the query as-is with a warning
        # TODO: Implement proper identifier replacement via security/identifier_replacer.py

        sanitized = query
        replacement_map = {}

        # Basic sanitization patterns (would be expanded in production)
        # Remove file paths
        import re
        # Windows paths: C:\Users\... or C:/Users/...
        sanitized = re.sub(r'[A-Za-z]:[/\\][^ \t\n\r\f\v<>|"\'\']+', '<PATH>', sanitized)
        # Unix paths: /home/user/ or \path\to\
        sanitized = re.sub(r'[/\\][a-zA-Z][a-zA-Z0-9_.-]+([/\\][a-zA-Z0-9_.-]+)*', '<PATH>', sanitized)

        # Remove hex strings that might be identifiers
        sanitized = re.sub(r'0x[0-9a-fA-F]+', '<HEX>', sanitized)

        return sanitized, replacement_map

    def unsanitize_response(self, response: str, replacement_map: Dict[str, str]) -> str:
        """Restore sanitized placeholders with original values."""
        # Reverse the replacements
        for original, placeholder in replacement_map.items():
            response = response.replace(placeholder, original)
        return response

    def search(
        self,
        query: str,
        model: str = DEFAULT_MODEL,
        max_results: int = 5,
        timeout: int = 30
    ) -> PerplexityResponse:
        """
        Perform a web search via Perplexity API.

        Args:
            query: The search query
            model: Perplexity model to use
            max_results: Maximum number of citations to return
            timeout: Request timeout in seconds

        Returns:
            PerplexityResponse with answer, citations, and metadata

        Raises:
            PerplexityAPIError: If the API request fails
        """
        import requests

        if model not in self.MODELS:
            raise PerplexityAPIError(
                f"Unknown model: {model}. "
                f"Available: {list(self.MODELS.keys())}"
            )

        # Sanitize query before external API call
        sanitized_query, replacement_map = self.sanitize_query(query)

        # Prepare request
        url = f"{self.API_BASE}/search"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.MODELS[model]["model"],
            "query": sanitized_query,
            "max_results": max_results,
        }

        start_time = datetime.now()

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout
            )

            response.raise_for_status()

            data = response.json()

            # Parse response - Perplexity API returns "results" array
            results_data = data.get("results", [])
            citations = []

            # Build answer from snippets (or return first snippet as answer)
            answer_parts = []
            for result in results_data:
                snippet = result.get("snippet", "")
                if snippet:
                    answer_parts.append(snippet)

                # Also add to citations
                citations.append(SearchResult(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=snippet,
                    score=0.0,  # Perplexity doesn't return scores
                    source="perplexity"
                ))

            # Use first snippet as primary answer, or concatenate all
            answer = answer_parts[0] if answer_parts else ""

            # Unsanitize answer (restore placeholders if any)
            answer = self.unsanitize_response(answer, replacement_map)

            # Calculate metadata
            latency_seconds = (datetime.now() - start_time).total_seconds()
            tokens_used = len(answer) // 4  # Rough estimate

            cost = self.MODELS[model]["cost_per_search"]

            return PerplexityResponse(
                answer=answer,
                citations=citations,
                model=model,
                tokens_used=tokens_used,
                cost=cost,
                latency_seconds=latency_seconds,
            )

        except requests.exceptions.Timeout:
            raise PerplexityAPIError(f"Request timed out after {timeout}s")
        except requests.exceptions.ConnectionError:
            raise PerplexityAPIError("Failed to connect to Perplexity API")
        except requests.exceptions.HTTPError as e:
            raise PerplexityAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
        except KeyError as e:
            raise PerplexityAPIError(f"Unexpected response format: {e}")
        except Exception as e:
            raise PerplexityAPIError(f"Unexpected error: {e}")

    def quick_search(self, query: str, timeout: int = 15) -> str:
        """
        Quick search for getting just the answer without citations.

        Args:
            query: Search query
            timeout: Request timeout in seconds

        Returns:
            The answer text only
        """
        response = self.search(query, model="sonar-small-online", max_results=3, timeout=timeout)
        return response.answer

    def get_citations_only(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Get just the citations from a search (for fact-checking).

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        response = self.search(query, max_results=max_results)
        return response.citations


# ============================================================================
# CLI Testing
# ============================================================================
# CLI usage disabled - use through gateway instead
# if __name__ == "__main__":
#     import sys
#
#     if len(sys.argv) < 2:
#         print("Usage: python perplexity_wrapper.py '<search query>'")
#         sys.exit(1)
#
#     wrapper = PerplexityWrapper()
#
#     query = " ".join(sys.argv[1:])
#
#     print(f"Searching: {query}")
#     print()
#
#     try:
#         response = wrapper.search(query, model="sonar-small-online")
#
#         print(f"Answer: {response.answer}")
#         print()
#         print(f"Citations ({len(response.citations)}):")
#         for i, citation in enumerate(response.citations, 1):
#             print(f"  {i}. {citation.title}")
#             print(f"     {citation.url}")
#             if citation.snippet:
#                 print(f"     {citation.snippet[:100]}...")
#             print()
#
#         print(f"\nMetadata:")
#         print(f"  Model: {response.model}")
#         print(f"  Tokens: ~{response.tokens_used}")
#         print(f"  Cost: ${response.cost:.4f}")
#         print(f"  Latency: {response.latency_seconds:.2f}s")
#
#     except PerplexityAPIError as e:
#         print(f"Error: {e}")
#         sys.exit(1)
