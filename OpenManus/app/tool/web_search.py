import asyncio
import collections
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse


import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from app.config import config
from app.logger import logger
from app.tool.base import BaseTool, ToolResult
from app.tool.search import (
    BaiduSearchEngine,
    BingSearchEngine,
    DuckDuckGoSearchEngine,
    GoogleSearchEngine,
    WebSearchEngine,
)
from app.tool.search.base import SearchItem
from app.tracer import traceable


# ── URL 规范化 / 去重 ───────────────────────────────────────────

def _normalize_url_for_dedup(url: str) -> str:
    """
    Normalize a URL for deduplication comparison.

    Strips www prefix, lowercases host, removes fragments and trailing slashes.
    Unwraps redirect/wrapper URLs (e.g., Baidu links) to compare the real target.
    Two URLs pointing to the same page should produce the same normalized form.
    """
    if not url:
        return ""
    # Unwrap redirect wrappers first
    url = _unwrap_redirect_url(url)
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Standardize path: empty → "/", strip trailing slash
    path = parsed.path.rstrip("/") or "/"
    # Reconstruct: scheme + netloc + path + query (keep query, drop fragment)
    return urlunparse((parsed.scheme.lower(), netloc, path, parsed.params, parsed.query, ""))


def _unwrap_redirect_url(url: str) -> str:
    """
    Unwrap redirect/wrapper URLs (e.g., Baidu's baidu.com/link?url=REAL_URL)
    to get the actual target URL. Returns the original if not a known wrapper.
    """
    if not url:
        return url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()

    # Baidu link redirect
    if "baidu.com" in netloc and parsed.path == "/link" and "url=" in parsed.query:
        from urllib.parse import parse_qs, unquote
        qs = parse_qs(parsed.query)
        real_urls = qs.get("url", [])
        if real_urls:
            return unquote(real_urls[0])
    return url


def _domain_from_url(url: str) -> str:
    """
    Extract a clean domain from a URL.
    Handles redirect/wrapper URLs (e.g., Baidu's baidu.com/link?url=REAL_URL).
    """
    if not url:
        return "unknown"
    # Unwrap redirect wrappers to get the real target
    url = _unwrap_redirect_url(url)
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or "unknown"


def _content_fingerprint(text: str, n_chars: int = 200) -> str:
    """
    A cheap content fingerprint for near-duplicate detection.
    Uses a truncated hash of the first n_chars of the text.
    """
    if not text:
        return ""
    normalized = " ".join(text[:n_chars].lower().split())
    return hashlib.md5(normalized.encode("utf-8", errors="ignore")).hexdigest()


class SearchResult(BaseModel):
    """Represents a single search result returned by a search engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(
        default="", description="Description or snippet of the search result"
    )
    source: str = Field(description="The search engine that provided this result")
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"


class SearchMetadata(BaseModel):
    """Metadata about the search operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_results: int = Field(description="Total number of results found")
    language: str = Field(description="Language code used for the search")
    country: str = Field(description="Country code used for the search")


class SearchResponse(ToolResult):
    """Structured response from the web search tool, inheriting ToolResult."""

    query: str = Field(description="The search query that was executed")
    results: List[SearchResult] = Field(
        default_factory=list, description="List of search results"
    )
    metadata: Optional[SearchMetadata] = Field(
        default=None, description="Metadata about the search"
    )

    @model_validator(mode="after")
    def populate_output(self) -> "SearchResponse":
        """Populate output or error fields based on search results."""
        if self.error:
            return self

        result_text = [f"Search results for '{self.query}':"]

        for i, result in enumerate(self.results, 1):
            # Add title with position number
            title = result.title.strip() or "No title"
            result_text.append(f"\n{i}. {title}")

            # Add URL with proper indentation
            result_text.append(f"   URL: {result.url}")

            # Add description if available
            if result.description.strip():
                result_text.append(f"   Description: {result.description}")

            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content[:1000].replace("\n", " ").strip()
                if len(result.raw_content) > 1000:
                    content_preview += "..."
                result_text.append(f"   Content: {content_preview}")

        # Add metadata at the bottom if available
        if self.metadata:
            result_text.extend(
                [
                    f"\nMetadata:",
                    f"- Total results: {self.metadata.total_results}",
                    f"- Language: {self.metadata.language}",
                    f"- Country: {self.metadata.country}",
                ]
            )

        self.output = "\n".join(result_text)
        return self


class WebContentFetcher:
    """Utility class for fetching web content."""

    @staticmethod
    async def fetch_content(url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch and extract the main content from a webpage.

        Args:
            url: The URL to fetch content from
            timeout: Request timeout in seconds

        Returns:
            Extracted text content or None if fetching fails
        """
        headers = {
            "WebSearch": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Use asyncio to run requests in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.get(url, headers=headers, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch content from {url}: HTTP {response.status_code}"
                )
                return None

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace and limit size (100KB max)
            text = " ".join(text.split())
            return text[:10000] if text else None

        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None


class WebSearch(BaseTool):
    """Search the web for information using various search engines."""

    name: str = "web_search"
    description: str = """Search the web for real-time information about any topic.
    This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
    If the primary search engine fails, it automatically falls back to alternative engines."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to the search engine.",
            },
            "num_results": {
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 5.",
                "default": 5,
            },
            "lang": {
                "type": "string",
                "description": "(optional) Language code for search results (default: en).",
                "default": "en",
            },
            "country": {
                "type": "string",
                "description": "(optional) Country code for search results (default: us).",
                "default": "us",
            },
            "fetch_content": {
                "type": "boolean",
                "description": "(optional) Whether to fetch full content from result pages. Default is false.",
                "default": False,
            },
        },
        "required": ["query"],
    }
    _search_engine: dict[str, WebSearchEngine] = {
        "google": GoogleSearchEngine(),
        "baidu": BaiduSearchEngine(),
        "duckduckgo": DuckDuckGoSearchEngine(),
        "bing": BingSearchEngine(),
    }
    content_fetcher: WebContentFetcher = WebContentFetcher()

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        lang: Optional[str] = None,
        country: Optional[str] = None,
        fetch_content: bool = False,
    ) -> SearchResponse:
        """
        Execute a Web search and return detailed search results.

        Args:
            query: The search query to submit to the search engine
            num_results: The number of search results to return (default: 5)
            lang: Language code for search results (default from config)
            country: Country code for search results (default from config)
            fetch_content: Whether to fetch content from result pages (default: False)

        Returns:
            A structured response containing search results and metadata
        """
        # Get settings from config
        retry_delay = (
            getattr(config.search_config, "retry_delay", 60)
            if config.search_config
            else 60
        )
        max_retries = (
            getattr(config.search_config, "max_retries", 3)
            if config.search_config
            else 3
        )

        # Use config values for lang and country if not specified
        if lang is None:
            lang = (
                getattr(config.search_config, "lang", "en")
                if config.search_config
                else "en"
            )

        if country is None:
            country = (
                getattr(config.search_config, "country", "us")
                if config.search_config
                else "us"
            )

        search_params = {"lang": lang, "country": country}

        # Try searching with retries when all engines fail
        for retry_count in range(max_retries + 1):
            results = await self._try_all_engines(query, num_results, search_params)

            if results:
                # Fetch content if requested
                if fetch_content:
                    results = await self._fetch_content_for_results(results)

                # Return a successful structured response
                return SearchResponse(
                    status="success",
                    query=query,
                    results=results,
                    metadata=SearchMetadata(
                        total_results=len(results),
                        language=lang,
                        country=country,
                    ),
                )

            if retry_count < max_retries:
                # All engines failed, wait and retry
                logger.warning(
                    f"All search engines failed. Waiting {retry_delay} seconds before retry {retry_count + 1}/{max_retries}..."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"All search engines failed after {max_retries} retries. Giving up."
                )

        # Return an error response
        return SearchResponse(
            query=query,
            error="All search engines failed to return results after multiple retries.",
            results=[],
        )

    async def multi_query_search(
        self,
        queries: List[str],
        num_results: int = 5,
        lang: Optional[str] = None,
        country: Optional[str] = None,
        fetch_content: bool = True,
        max_total: int = 12,
    ) -> SearchResponse:
        """
        Search using multiple query variants in parallel, deduplicate results,
        and rank by source diversity (domain spread).

        Key improvements over execute():
        1. Parallel query search: all query variants fire concurrently
        2. URL dedup: identical pages (normalized URL) only appear once
        3. Content dedup: near-duplicate content is filtered
        4. Source diversity: ensures different domains get distributed fairly,
           ranking prefers results from domains not yet represented
        5. Scored ranking: combines search rank, cross-query consensus, and domain diversity

        Args:
            queries: List of optimized search query strings
            num_results: Per-query result count passed to each engine
            lang: Language code
            country: Country code
            fetch_content: Whether to fetch page content
            max_total: Maximum total results to return after dedup

        Returns:
            SearchResponse with deduplicated, diversity-ranked results
        """
        if not queries:
            return SearchResponse(
                query="", error="No queries provided.", results=[]
            )

        primary_query = queries[0]
        if lang is None:
            lang = (
                getattr(config.search_config, "lang", "en")
                if config.search_config else "en"
            )
        if country is None:
            country = (
                getattr(config.search_config, "country", "us")
                if config.search_config else "us"
            )

        # ── Phase 1: parallel search across all queries ──
        logger.info(
            f"🔎 Multi-query search: {len(queries)} queries in parallel: {queries}"
        )

        async def _search_one(q: str) -> List[SearchResult]:
            max_retries = (
                getattr(config.search_config, "max_retries", 3)
                if config.search_config else 3
            )
            retry_delay = (
                getattr(config.search_config, "retry_delay", 60)
                if config.search_config else 60
            )
            search_params = {"lang": lang, "country": country}
            for attempt in range(max_retries + 1):
                results = await self._try_all_engines(q, num_results, search_params)
                if results:
                    # Tag with the query that produced them
                    for r in results:
                        r.description = f"[q: {q[:40]}...] {r.description or ''}"
                    return results
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
            return []

        # All queries fire concurrently
        query_results_lists = await asyncio.gather(*[_search_one(q) for q in queries])

        # ── Phase 2: URL dedup ──
        seen_urls: Dict[str, SearchResult] = {}  # normalized_url → result
        url_dedup_order: List[str] = []

        for results in query_results_lists:
            for r in results:
                norm = _normalize_url_for_dedup(r.url)
                if norm and norm not in seen_urls:
                    seen_urls[norm] = r
                    url_dedup_order.append(norm)

        logger.info(
            f"URL dedup: {sum(len(r) for r in query_results_lists)} raw → "
            f"{len(url_dedup_order)} unique URLs"
        )

        # ── Phase 3: content dedup ──
        content_seen: Dict[str, SearchResult] = {}
        deduped_results: List[SearchResult] = []
        for norm in url_dedup_order:
            r = seen_urls[norm]
            # Only dedup if there IS raw_content to compare
            if r.raw_content:
                fp = _content_fingerprint(r.raw_content)
                if fp and fp in content_seen:
                    # Same content from different URL → keep the shorter URL
                    continue
                if fp:
                    content_seen[fp] = r
            deduped_results.append(r)

        logger.info(
            f"Content dedup: {len(url_dedup_order)} URL-unique → "
            f"{len(deduped_results)} content-unique"
        )

        # ── Phase 4: source diversity scoring ──
        ranked = self._rank_by_diversity(deduped_results, max_total)

        logger.info(
            f"Diversity ranking: {len(deduped_results)} → {len(ranked)} results "
            f"({len(set(_domain_from_url(r.url) for r in ranked))} unique domains)"
        )

        # ── Phase 5: fetch content if needed ──
        if fetch_content:
            # Only fetch for results that don't already have it
            needs_fetch = [r for r in ranked if not r.raw_content]
            if needs_fetch:
                fetched = await self._fetch_content_for_results(needs_fetch)
                # Merge back
                fetch_map = {_normalize_url_for_dedup(r.url): r.raw_content for r in fetched}
                for r in ranked:
                    norm = _normalize_url_for_dedup(r.url)
                    if norm in fetch_map and fetch_map[norm]:
                        r.raw_content = fetch_map[norm]

        # Reposition after dedup
        for i, r in enumerate(ranked, 1):
            r.position = i

        return SearchResponse(
            status="success",
            query=primary_query,
            results=ranked,
            metadata=SearchMetadata(
                total_results=len(ranked),
                language=lang,
                country=country,
            ),
        )

    def _rank_by_diversity(
        self,
        results: List[SearchResult],
        max_total: int = 12,
    ) -> List[SearchResult]:
        """
        Rank results with a diversity-first approach.

        Scoring factors:
        - original_position: lower (better-ranked) = higher score
        - cross_query_consensus: a URL that appeared under multiple queries
          gets a bonus
        - domain_diversity: domains that haven't been picked yet get a bonus,
          preventing a single site from dominating the top results

        Algorithm: greedy round-robin across domains
        """
        if not results:
            return []

        # Group results by domain, keeping original order within each domain
        domain_buckets: Dict[str, List[SearchResult]] = collections.OrderedDict()
        domain_order: List[str] = []

        for r in results:
            dom = _domain_from_url(r.url)
            if dom not in domain_buckets:
                domain_buckets[dom] = []
                domain_order.append(dom)
            domain_buckets[dom].append(r)

        # Greedy round-robin: pick one from each domain, then another round
        ranked: List[SearchResult] = []
        indices = {dom: 0 for dom in domain_buckets}

        while len(ranked) < max_total:
            added_this_round = False
            for dom in domain_order:
                if indices[dom] < len(domain_buckets[dom]):
                    ranked.append(domain_buckets[dom][indices[dom]])
                    indices[dom] += 1
                    added_this_round = True
                    if len(ranked) >= max_total:
                        break
            if not added_this_round:
                break  # all domains exhausted

        return ranked

    async def _try_all_engines(
        self, query: str, num_results: int, search_params: Dict[str, Any]
    ) -> List[SearchResult]:
        """Try all search engines in the configured order."""
        engine_order = self._get_engine_order()
        failed_engines = []

        for engine_name in engine_order:
            engine = self._search_engine[engine_name]
            logger.info(f"🔎 Attempting search with {engine_name.capitalize()}...")
            try:
                search_items = await self._perform_search_with_engine(
                    engine, query, num_results, search_params
                )
            except RetryError as e:
                # Keep falling back to other engines instead of aborting the whole search.
                failed_engines.append(engine_name)
                root_error = e.last_attempt.exception() if e.last_attempt else e
                logger.warning(
                    f"{engine_name.capitalize()} failed after retries: {root_error}"
                )
                continue
            except Exception as e:
                failed_engines.append(engine_name)
                logger.warning(f"{engine_name.capitalize()} failed: {e}")
                continue

            if not search_items:
                failed_engines.append(engine_name)
                continue

            if failed_engines:
                logger.info(
                    f"Search successful with {engine_name.capitalize()} after trying: {', '.join(failed_engines)}"
                )

            # Transform search items into structured results
            return [
                SearchResult(
                    position=i + 1,
                    url=item.url,
                    title=item.title
                    or f"Result {i+1}",  # Ensure we always have a title
                    description=item.description or "",
                    source=engine_name,
                )
                for i, item in enumerate(search_items)
            ]

        if failed_engines:
            logger.error(f"All search engines failed: {', '.join(failed_engines)}")
        return []

    async def _fetch_content_for_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results:
            return []

        # Create tasks for each result
        tasks = [self._fetch_single_result_content(result) for result in results]

        # Type annotation to help type checker
        fetched_results = await asyncio.gather(*tasks)

        # Explicit validation of return type
        return [
            (
                result
                if isinstance(result, SearchResult)
                else SearchResult(**result.dict())
            )
            for result in fetched_results
        ]

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url:
            content = await self.content_fetcher.fetch_content(result.url)
            if content:
                result.raw_content = content
        return result

    def _get_engine_order(self) -> List[str]:
        """Determines the order in which to try search engines."""
        preferred = (
            getattr(config.search_config, "engine", "google").lower()
            if config.search_config
            else "google"
        )
        fallbacks = (
            [engine.lower() for engine in config.search_config.fallback_engines]
            if config.search_config
            and hasattr(config.search_config, "fallback_engines")
            else []
        )

        # Start with preferred engine, then fallbacks, then remaining engines
        engine_order = [preferred] if preferred in self._search_engine else []
        engine_order.extend(
            [
                fb
                for fb in fallbacks
                if fb in self._search_engine and fb not in engine_order
            ]
        )
        engine_order.extend([e for e in self._search_engine if e not in engine_order])

        return engine_order

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, Any],
    ) -> List[SearchItem]:
        """Execute search with the given engine and parameters."""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(
                engine.perform_search(
                    query,
                    num_results=num_results,
                    lang=search_params.get("lang"),
                    country=search_params.get("country"),
                )
            ),
        )


    # ── 意图识别 + Query 改写 + 智能搜索 ─────────────────────────

    @traceable(name="intent_analysis", run_type="chain")
    async def _analyze_search_intent(self, prompt: str) -> dict:
        """Use LLM to decide if search is needed and generate optimized queries.

        Delegates to the shared intent_analyzer module for the actual LLM call.
        Backward-compatible with search_with_intent().

        Returns:
            {"should_search": bool, "search_queries": [str], "reasoning": str}
        """
        try:
            from app.tool.intent_analyzer import analyze_intent

            intent = await analyze_intent(prompt)

            should_search = intent.get("tool") == "web_search"
            return {
                "should_search": should_search,
                "search_queries": intent.get("search_queries", [prompt]),
                "reasoning": intent.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning(f"Intent analysis failed, defaulting to search: {e}")
            return {"should_search": True, "search_queries": [prompt], "reasoning": "analysis failed, fallback"}

    async def search_with_intent(
        self,
        prompt: str,
        *,
        num_results: int = 5,
        fetch_content: bool = True,
        max_total: int = 10,
    ) -> dict:
        """Intelligent search: analyze intent, rewrite queries, then search.

        This is the recommended entry point for user-facing search. It handles
        the full pipeline internally — intent analysis, query rewriting, and
        multi-query search with dedup and diversity ranking.

        Args:
            prompt: Raw user question (conversational, any language).
            num_results: Per-query result count passed to each engine.
            fetch_content: Whether to fetch page content for each result.
            max_total: Maximum total results to return after dedup.

        Returns:
            dict with keys:
                should_search: bool
                reasoning: str
                search_queries: [str] — the optimized queries actually used
                results: [dict] — {title, url, description, content_preview, source}
                total_results: int
                unique_domains: int
        """
        intent = await self._analyze_search_intent(prompt)

        base = {
            "should_search": intent["should_search"],
            "reasoning": intent["reasoning"],
            "search_queries": intent["search_queries"],
            "results": [],
            "total_results": 0,
            "unique_domains": 0,
        }

        if not intent["should_search"] or not intent["search_queries"]:
            return base

        search_response = await self.multi_query_search(
            queries=intent["search_queries"],
            num_results=num_results,
            fetch_content=fetch_content,
            max_total=max_total,
        )

        if not search_response.results:
            return base

        simplified = []
        for r in search_response.results:
            simplified.append({
                "title": r.title,
                "url": r.url,
                "description": r.description or "",
                "content_preview": (r.raw_content or "")[:600],
                "source": r.source,
            })

        domains = set(_domain_from_url(r["url"]) for r in simplified)

        return {
            **base,
            "results": simplified,
            "total_results": len(simplified),
            "unique_domains": len(domains),
        }


if __name__ == "__main__":
    web_search = WebSearch()
    search_response = asyncio.run(
        web_search.execute(
            query="Python programming", fetch_content=True, num_results=1
        )
    )
    print(search_response.to_tool_result())
