"""
SearXNG search integration for Deliberate AI
"""

import requests
import logging
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Load default URL from settings if available
DEFAULT_SEARXNG_URL = "http://localhost:8080/search"
try:
    settings_path = Path(__file__).parent / "settings.json"
    if settings_path.exists():
        with open(settings_path, "r") as f:
            settings = json.load(f)
            DEFAULT_SEARXNG_URL = settings.get("search_url", DEFAULT_SEARXNG_URL)
except Exception as e:
    logger.debug(f"Could not load search_url from settings: {e}")


def check_searxng_reachable(url: Optional[str] = None) -> bool:
    """Check if SearXNG endpoint is reachable."""
    if url is None:
        url = DEFAULT_SEARXNG_URL
    try:
        response = requests.get(url, params={"q": "test"}, timeout=5)
        return response.status_code == 200
    except (requests.RequestException, requests.Timeout):
        return False


def search_searxng(query: str, url: Optional[str] = None, num_results: int = 5) -> list:
    """
    Search SearXNG and return formatted results.

    Returns list of dicts with 'title' and 'snippet' keys.
    Returns empty list on error.
    """
    if url is None:
        url = DEFAULT_SEARXNG_URL
    """
    Search SearXNG and return formatted results.

    Returns list of dicts with 'title' and 'snippet' keys.
    Returns empty list on error.
    """
    try:
        response = requests.get(url, params={"q": query, "format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        for result in data.get("results", [])[:num_results]:
            results.append(
                {
                    "title": result.get("title", ""),
                    "snippet": result.get("content", "") or result.get("snippet", ""),
                }
            )

        return results
    except (requests.RequestException, requests.Timeout, ValueError) as e:
        logger.warning(f"SearXNG search failed for query '{query}': {e}")
        return []


def generate_search_queries(text: str, num_queries: int = 3) -> list:
    """Generate search queries from input text (simple extraction)."""
    # Simple keyword extraction - could be enhanced with LLM
    words = text.lower().split()
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "and",
        "but",
        "or",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "not",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "any",
        "this",
        "that",
        "these",
        "those",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "me",
        "him",
        "us",
        "them",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "myself",
        "yourself",
        "himself",
        "herself",
        "itself",
        "ourselves",
        "themselves",
    }

    # Extract meaningful words/phrases
    keywords = [w for w in words if w not in stop_words and len(w) > 3]

    queries = []
    if len(keywords) >= 3:
        queries.append(" ".join(keywords[:3]))
        queries.append(" ".join(keywords[1:4]))
        queries.append(" ".join(keywords[2:5]))
    elif len(keywords) > 0:
        queries.append(" ".join(keywords))
        if len(keywords) > 1:
            queries.append(" ".join(keywords[:2]))

    return queries[:num_queries]


def format_search_results(results: list) -> str:
    """Format search results for injection into prompts."""
    if not results:
        return ""

    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. {result['title']}\n   {result['snippet']}")

    return "\n\n".join(formatted)


def parallel_search(queries: list, url: Optional[str] = None) -> dict:
    """
    Run multiple searches in parallel and return results by query.
    """
    import concurrent.futures

    if url is None:
        url = DEFAULT_SEARXNG_URL

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(queries)) as executor:
        future_to_query = {executor.submit(search_searxng, q, url): q for q in queries}

        for future in concurrent.futures.as_completed(future_to_query):
            query = future_to_query[future]
            try:
                results[query] = future.result()
            except Exception as e:
                logger.warning(f"Search for '{query}' failed: {e}")
                results[query] = []

    return results
