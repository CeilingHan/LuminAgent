from typing import List
from urllib.parse import urljoin, urlparse

from baidusearch.baidusearch import search

from app.tool.search.base import SearchItem, WebSearchEngine

BAIDU_BASE_URL = "https://www.baidu.com"


class BaiduSearchEngine(WebSearchEngine):
    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Baidu search engine.

        Returns results formatted according to SearchItem model.
        """
        raw_results = search(query, num_results=num_results)

        # Convert raw results to SearchItem format
        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, str):
                # If it's just a URL
                results.append(
                    SearchItem(title=f"Baidu Result {i+1}", url=self._normalize_url(item), description=None)
                )
            elif isinstance(item, dict):
                # If it's a dictionary with details
                results.append(
                    SearchItem(
                        title=item.get("title", f"Baidu Result {i+1}"),
                        url=self._normalize_url(item.get("url", "")),
                        description=item.get("abstract", None),
                    )
                )
            else:
                # Try to get attributes directly
                try:
                    results.append(
                        SearchItem(
                            title=getattr(item, "title", f"Baidu Result {i+1}"),
                            url=self._normalize_url(getattr(item, "url", "")),
                            description=getattr(item, "abstract", None),
                        )
                    )
                except Exception:
                    # Fallback to a basic result
                    results.append(
                        SearchItem(
                            title=f"Baidu Result {i+1}", url=self._normalize_url(str(item)), description=None
                        )
                    )

        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Ensure URL is absolute, adding scheme and host if relative."""
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme:
            # Relative URL — prepend Baidu base
            return urljoin(BAIDU_BASE_URL, url)
        return url
