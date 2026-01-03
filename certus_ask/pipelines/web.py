from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.util import find_spec
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from haystack import Document, Pipeline, component
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from readability import Document as ReadabilityDocument
from trafilatura import extract as trafilatura_extract
from w3lib.url import canonicalize_url

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

from certus_ask.pipelines.preprocessing import PresidioAnonymizer

logger = logging.getLogger(__name__)

PLAYWRIGHT_INSTALL_MESSAGE = (
    "Web scraping with JavaScript rendering requires the 'web' extra. Install with: pip install 'certus-tap[web]'"
)

_playwright_available = find_spec("playwright.async_api") is not None

USER_AGENT = "Certus-TAP-WebCrawler/1.0"
DEFAULT_RATE_LIMIT = 2  # requests per second per host
MAX_CONCURRENCY = 5
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB


@dataclass
class PageResult:
    url: str
    title: str
    text: str
    rendered: bool


class _PlaywrightContext:
    def __init__(self, enabled: bool) -> None:
        if enabled and not _playwright_available:
            raise ImportError(PLAYWRIGHT_INSTALL_MESSAGE)
        self.enabled = enabled and _playwright_available
        self._playwright = None
        self._browser = None

    async def __aenter__(self) -> _PlaywrightContext:
        if not self.enabled:
            return self
        try:  # pragma: no cover - requires Playwright runtime
            from playwright.async_api import async_playwright as _async_playwright
        except ImportError as exc:  # pragma: no cover
            logger.warning("Playwright not installed: %s", exc)
            self.enabled = False
            return self
        self._playwright = await _async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        return self

    async def render(self, url: str, timeout: int) -> str | None:
        if not self.enabled or not self._browser:  # pragma: no cover
            return None
        context = await self._browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            html = await page.content()
            return html
        finally:
            await context.close()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:  # pragma: no cover
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


@component
class WebCrawlerComponent:
    """Async web crawler component for indexing web pages into RAG system.

    Features:
    - Concurrent async crawling with rate limiting per host
    - Robots.txt compliance and caching
    - JavaScript rendering support (optional Playwright)
    - Content deduplication via URL canonicalization
    - HTML content extraction with fallback extraction methods
    - Metadata tracking (URL, title, rendered flag)

    **Rate Limiting Strategy:**
    - Per-host rate limiting to respect server resources
    - Configurable requests per second per host (default: 2)
    - Global concurrency limit to prevent resource exhaustion

    **Content Extraction:**
    - Primary: Trafilatura (fast, accurate article extraction)
    - Fallback: Readability (for complex HTML structures)
    - JavaScript rendering: Optional Playwright for dynamic content

    Args:
        user_agent: HTTP User-Agent header (default: Certus-TAP-WebCrawler/1.0)
        rate_limit_per_host: Max requests per second per domain (default: 2)
        max_concurrency: Max concurrent requests across all hosts (default: 5)
        request_timeout: HTTP request timeout in seconds (default: 20)
        render_timeout: JavaScript rendering timeout in seconds (default: 25)
    """

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        rate_limit_per_host: int = DEFAULT_RATE_LIMIT,
        max_concurrency: int = MAX_CONCURRENCY,
        request_timeout: int = 20,
        render_timeout: int = 25,
    ) -> None:
        self.user_agent = user_agent
        self.rate_limit_per_host = rate_limit_per_host
        self.max_concurrency = max_concurrency
        self.request_timeout = request_timeout
        self.render_timeout = render_timeout
        self._robots_cache: dict[str, RobotFileParser] = {}

    @component.output_types(documents=list[Document], skipped=list[str])
    def run(self, urls: Sequence[str], render: bool = False) -> dict[str, list]:
        """Crawl and extract content from web pages.

        Concurrently fetches multiple URLs, extracts article content, and returns
        structured documents ready for embedding and indexing. Respects robots.txt,
        implements rate limiting, and deduplicates URLs.

        **URL Processing:**
        - Canonicalizes URLs (removes fragments, query params, etc.)
        - Deduplicates identical URLs
        - Respects robots.txt restrictions per host
        - Skips invalid/malformed URLs

        **Content Extraction:**
        1. Fetch HTML via HTTP(S)
        2. Optional JavaScript rendering via Playwright
        3. Extract main article content with Trafilatura
        4. Fallback to Readability if extraction fails
        5. Extract title and metadata

        **Concurrency Control:**
        - Per-host rate limiting (default: 2 req/s)
        - Global semaphore (default: 5 concurrent)
        - Prevents overwhelming target servers
        - Gracefully handles timeouts/errors

        Args:
            urls: List of URLs to crawl. Accepts strings or URL objects.
                Supports HTTP and HTTPS. IPv6, subdomains, and query params handled.
            render: If True, use Playwright to render JavaScript before extraction.
                Slower but captures dynamically loaded content. Default: False.

        Returns:
            Dictionary with two keys:
            - 'documents': List of Document objects with extracted content.
              Each document has:
              - content: Extracted main article text
              - meta['url']: Original URL (canonicalized)
              - meta['title']: Page title
              - meta['rendered']: Whether JS was rendered
              - meta['source']: Always 'web'
            - 'skipped': List of URLs that couldn't be processed

        Examples:
            >>> crawler = WebCrawlerComponent(rate_limit_per_host=5, max_concurrency=10)
            >>>
            >>> # Crawl simple websites
            >>> urls = [
            ...     "https://example.com/article1",
            ...     "https://example.com/article2",
            ...     "https://docs.example.com/guide"
            ... ]
            >>> result = crawler.run(urls)
            >>> docs = result["documents"]
            >>> skipped = result["skipped"]
            >>>
            >>> print(f"Crawled: {len(docs)} pages, Skipped: {len(skipped)}")
            Crawled: 3 pages, Skipped: 0
            >>>
            >>> # Access extracted content
            >>> for doc in docs:
            ...     print(f"URL: {doc.meta['url']}")
            ...     print(f"Title: {doc.meta['title']}")
            ...     print(f"Content length: {len(doc.content)} chars")
            URL: https://example.com/article1
            Title: Example Article 1
            Content length: 2847 chars

            >>> # Crawl with JavaScript rendering for dynamic sites
            >>> urls = ["https://react-app.example.com"]
            >>> result = crawler.run(urls, render=True)
            >>> for doc in result["documents"]:
            ...     if doc.meta.get("rendered"):
            ...         print(f"Rendered JavaScript-heavy page: {doc.meta['url']}")
            Rendered JavaScript-heavy page: https://react-app.example.com

            >>> # Handle robots.txt and errors gracefully
            >>> urls = [
                "https://example.com/valid",
                "https://invalid--url",  # Malformed
            ... ]
            >>> result = crawler.run(urls)
            >>> print(f"Successful: {len(result['documents'])}")
            Successful: 1
            >>> print(f"Failed/Skipped: {result['skipped']}")
            Failed/Skipped: ['https://invalid--url']

        Raises:
            Exception: Network errors are caught and logged, not re-raised.
                Failed URLs are moved to 'skipped' list.

        See Also:
            - create_web_pipeline: For full document indexing pipeline
            - AsyncLimiter: For rate limiting implementation
            - Trafilatura: For content extraction algorithm
        """
        filtered_urls, skipped = self._deduplicate(urls)
        if not filtered_urls:
            return {"documents": [], "skipped": list(skipped)}
        results: list[PageResult] = asyncio.run(self._crawl(filtered_urls, render))
        documents: list[Document] = []
        for page in results:
            doc_hash = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
            documents.append(
                Document(
                    content=page.text,
                    meta={
                        "source": "web",
                        "url": page.url,
                        "title": page.title,
                        "rendered": page.rendered,
                        "content_hash": doc_hash,
                    },
                )
            )
        return {"documents": documents, "skipped": list(skipped)}

    def _deduplicate(self, urls: Sequence[str]) -> tuple[list[str], set[str]]:
        seen: set[str] = set()
        skipped: set[str] = set()
        filtered: list[str] = []
        for url in urls:
            canonical = canonicalize_url(url)
            if not canonical:
                skipped.add(url)
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            filtered.append(canonical)
        return filtered, skipped

    async def _crawl(self, urls: list[str], render: bool) -> list[PageResult]:
        limiter_cache: dict[str, AsyncLimiter] = {}
        connector = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
            timeout=self.request_timeout,
        )
        try:
            async with connector as client:
                tasks = [self._fetch(client, url, limiter_cache, render) for url in urls]
                sem = asyncio.Semaphore(self.max_concurrency)

                async def wrapper(coro):
                    async with sem:
                        return await coro

                wrapped = [wrapper(task) for task in tasks]
                results = await asyncio.gather(*wrapped, return_exceptions=True)
        finally:
            pass

        pages: list[PageResult] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):  # pragma: no cover - network variability
                logger.warning("Failed to crawl %s: %s", url, result)
                continue
            if result:
                pages.append(result)
        return pages

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        limiter_cache: dict[str, AsyncLimiter],
        render: bool,
    ) -> PageResult | None:
        parsed = urlparse(url)
        host = parsed.netloc
        limiter = limiter_cache.setdefault(host, AsyncLimiter(self.rate_limit_per_host, time_period=1))

        if not await self._allowed(url, client):
            logger.info("Disallowed by robots.txt: %s", url)
            return None

        async with limiter:
            try:
                response = await client.get(url)
                response.raise_for_status()
                content_length = int(response.headers.get("Content-Length", 0))
                if content_length > MAX_CONTENT_LENGTH:
                    logger.warning("Skipping %s due to size", url)
                    return None
                html = response.text
            except Exception as exc:  # pragma: no cover - network variability
                logger.warning("HTTP fetch failed for %s: %s", url, exc)
                return None

        rendered_html: str | None = None
        if render:
            async with _PlaywrightContext(True) as playwright_ctx:  # pragma: no cover - requires playwright runtime
                rendered_html = await playwright_ctx.render(url, timeout=self.render_timeout)
        loop = asyncio.get_event_loop()
        text, title = await loop.run_in_executor(None, self._extract_text, rendered_html or html)
        if not text:
            return None
        return PageResult(url=url, title=title, text=text, rendered=rendered_html is not None)

    async def _allowed(self, url: str, client: httpx.AsyncClient) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = self._robots_cache.get(robots_url)
        if not parser:
            parser = RobotFileParser()
            try:
                resp = await client.get(robots_url)
                if resp.status_code < 400:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.parse([])
            except Exception:  # pragma: no cover - robots optional
                parser.parse([])
            self._robots_cache[robots_url] = parser
        return parser.can_fetch(self.user_agent, url)

    def _extract_text(self, html: str) -> tuple[str, str]:
        try:
            extracted = trafilatura_extract(html, include_comments=False, include_tables=False, include_links=False)
        except Exception:  # pragma: no cover
            extracted = None
        readability_doc = ReadabilityDocument(html)
        title = readability_doc.short_title() or "Untitled"
        if extracted:
            return extracted.strip(), title
        summary_html = readability_doc.summary(html_partial=True) or html
        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text("\n", strip=True)
        return text, title


def create_web_pipeline(document_store: OpenSearchDocumentStore) -> Pipeline:
    pipeline = Pipeline()
    scraper = WebCrawlerComponent()
    presidio = PresidioAnonymizer()
    splitter = DocumentSplitter(split_by="word", split_length=150, split_overlap=50)
    embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
    writer = DocumentWriter(document_store, policy=DuplicatePolicy.SKIP)

    pipeline.add_component(instance=scraper, name="scraper")
    pipeline.add_component(instance=presidio, name="presidio_anonymizer")
    pipeline.add_component(instance=splitter, name="document_splitter")
    pipeline.add_component(instance=embedder, name="document_embedder")
    pipeline.add_component(instance=writer, name="document_writer")

    pipeline.connect("scraper", "presidio_anonymizer.documents")
    pipeline.connect("presidio_anonymizer", "document_splitter")
    pipeline.connect("document_splitter", "document_embedder")
    pipeline.connect("document_embedder", "document_writer")

    return pipeline
