from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from multiprocessing import Process, Queue
from typing import ClassVar
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from haystack import Document, Pipeline, component
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from readability import Document as ReadabilityDocument
from trafilatura import extract as trafilatura_extract
from w3lib.url import canonicalize_url

from certus_ask.pipelines.preprocessing import PresidioAnonymizer

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

# Import guards for optional web scraping dependencies
SCRAPY_INSTALL_MESSAGE = (
    "Web scraping with Scrapy requires the 'web' extra. Install with: pip install 'certus-tap[web]'"
)

try:
    from scrapy import Request, Spider
    from scrapy.crawler import CrawlerProcess
    from scrapy.linkextractors import LinkExtractor
    from scrapy.utils.log import configure_logging
except ImportError as exc:
    raise ImportError(SCRAPY_INSTALL_MESSAGE) from exc

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    url: str
    title: str
    text: str


class CrawlProcessError(RuntimeError):
    """Raised when the crawl worker exits without returning results."""

    base_message = "Crawler process failed"

    def __init__(self, *, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__()

    def __str__(self) -> str:
        if self.detail:
            return f"{self.base_message}: {self.detail}"
        return self.base_message


class TAPSpider(Spider):
    name = "tap_crawler"

    custom_settings: ClassVar[dict[str, object]] = {
        "ROBOTSTXT_OBEY": True,
        "DEPTH_PRIORITY": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "LOG_ENABLED": False,
    }

    def __init__(
        self,
        items: list[CrawlResult],
        skipped: set[str],
        start_urls: Sequence[str],
        allowed_domains: Iterable[str] | None = None,
        allow_patterns: Iterable[str] | None = None,
        deny_patterns: Iterable[str] | None = None,
        max_pages: int = 100,
        max_depth: int = 1,
        render: bool = False,
        user_agent: str = "Certus-TAP-ScrapyCrawler/1.0",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.start_urls = list(start_urls)
        self.allowed_domains = list(allowed_domains) if allowed_domains else None
        self.allow_patterns = list(allow_patterns) if allow_patterns else None
        self.deny_patterns = list(deny_patterns) if deny_patterns else None
        self.max_pages = max(1, max_pages)
        self.max_depth = max(0, max_depth)
        self.render = render
        self.user_agent = user_agent
        self.items = items
        self.skipped = skipped
        self.pages_seen = 0
        self.link_extractor = LinkExtractor(
            allow=self.allow_patterns,
            deny=self.deny_patterns,
            allow_domains=self.allowed_domains,
        )

        # Adjust settings dynamically
        delay = 1.0 / kwargs.get("rate_limit_per_host", 2)
        self.custom_settings = {
            **self.custom_settings,
            "DOWNLOAD_DELAY": delay,
            "CONCURRENT_REQUESTS_PER_DOMAIN": kwargs.get("rate_limit_per_host", 2),
            "DEPTH_LIMIT": self.max_depth,
            "USER_AGENT": self.user_agent,
        }
        if self.render:
            self.custom_settings.update({
                "DOWNLOAD_HANDLERS": {
                    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                },
                "PLAYWRIGHT_BROWSER_TYPE": "chromium",
                "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
                "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            })

    def start_requests(self):
        for url in self.start_urls:
            meta = self._request_meta()
            yield Request(url, callback=self.parse, meta=meta, errback=self._handle_error)

    def _handle_error(self, failure):  # pragma: no cover - network variability
        url = failure.request.url
        logger.warning("Failed to fetch %s: %s", url, failure.value)
        self.skipped.add(url)

    def _append_item(self, response):
        text, title = self._extract_text(response.text)
        if not text.strip():
            self.skipped.add(response.url)
            return
        self.items.append(
            CrawlResult(
                url=response.url,
                title=title,
                text=text,
            )
        )

    def _request_meta(self):
        if not self.render:
            return {}
        return {
            "playwright": True,
        }

    def parse(self, response):
        if self.pages_seen >= self.max_pages:
            return
        self.pages_seen += 1
        self._append_item(response)

        if response.meta.get("depth", 0) >= self.max_depth:
            return
        for link in self.link_extractor.extract_links(response):
            if self.pages_seen >= self.max_pages:
                break
            meta = self._request_meta()
            yield response.follow(link.url, callback=self.parse, meta=meta, errback=self._handle_error)

    @staticmethod
    def _extract_text(html: str) -> tuple[str, str]:
        try:
            extracted = trafilatura_extract(
                html,
                include_comments=False,
                include_tables=False,
                include_links=False,
            )
        except Exception:
            extracted = None
        readability_doc = ReadabilityDocument(html)
        title = readability_doc.short_title() or "Untitled"
        if extracted:
            return extracted.strip(), title
        summary_html = readability_doc.summary(html_partial=True) or html
        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text("\n", strip=True)
        return text, title


@component
class ScrapyCrawlerComponent:
    def __init__(
        self,
        user_agent: str = "Certus-TAP-ScrapyCrawler/1.0",
        rate_limit_per_host: int = 2,
    ) -> None:
        self.user_agent = user_agent
        self.rate_limit_per_host = rate_limit_per_host
        configure_logging()

    @component.output_types(documents=list[Document], skipped=list[str])
    def run(
        self,
        seed_urls: Sequence[str],
        allowed_domains: Iterable[str] | None = None,
        allow_patterns: Iterable[str] | None = None,
        deny_patterns: Iterable[str] | None = None,
        max_pages: int = 100,
        max_depth: int = 1,
        render: bool = False,
    ) -> dict:
        canonical_urls = self._canonicalize(seed_urls)
        if not canonical_urls:
            return {"documents": [], "skipped": list(set(seed_urls))}

        allowed_domains = (
            allowed_domains if allowed_domains is not None else {urlparse(url).netloc for url in canonical_urls}
        )
        queue: Queue = Queue()
        process = Process(
            target=self._crawl_worker,
            kwargs={
                "queue": queue,
                "canonical_urls": canonical_urls,
                "allowed_domains": list(allowed_domains) if allowed_domains else None,
                "allow_patterns": list(allow_patterns) if allow_patterns else None,
                "deny_patterns": list(deny_patterns) if deny_patterns else None,
                "max_pages": max_pages,
                "max_depth": max_depth,
                "render": render,
            },
        )
        process.start()
        process.join()
        if queue.empty():
            raise CrawlProcessError(detail="no output")
        payload = queue.get()
        if error := payload.get("error"):
            raise CrawlProcessError(detail=error)
        items_data = payload.get("items", [])
        skipped = set(payload.get("skipped", []))
        items = [CrawlResult(**item) for item in items_data]

        documents: list[Document] = []
        for page in items:
            content_hash = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
            documents.append(
                Document(
                    content=page.text,
                    meta={
                        "source": "web",
                        "url": page.url,
                        "title": page.title,
                        "content_hash": content_hash,
                        "crawler": "scrapy",
                    },
                )
            )
        return {"documents": documents, "skipped": list(skipped)}

    @staticmethod
    def _canonicalize(urls: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        canonical: list[str] = []
        for url in urls:
            canon = canonicalize_url(url)
            if not canon or canon in seen:
                continue
            canonical.append(canon)
            seen.add(canon)
        return canonical

    def _crawl_worker(
        self,
        *,
        queue: Queue,
        canonical_urls: list[str],
        allowed_domains: list[str] | None,
        allow_patterns: list[str] | None,
        deny_patterns: list[str] | None,
        max_pages: int,
        max_depth: int,
        render: bool,
    ) -> None:
        items: list[CrawlResult] = []
        skipped: set[str] = set()
        allowed_domains_list = [d for d in allowed_domains or [] if d]
        process = CrawlerProcess()
        try:
            process.crawl(
                TAPSpider,
                items=items,
                skipped=skipped,
                start_urls=canonical_urls,
                allowed_domains=allowed_domains_list if allowed_domains_list else None,
                allow_patterns=allow_patterns,
                deny_patterns=deny_patterns,
                max_pages=max_pages,
                max_depth=max_depth,
                render=render,
                user_agent=self.user_agent,
                rate_limit_per_host=self.rate_limit_per_host,
            )
            process.start()
            process.join()
            queue.put({
                "items": [item.__dict__ for item in items],
                "skipped": list(skipped),
            })
        except Exception as exc:  # pragma: no cover - delegated to child proc
            queue.put({"error": str(exc)})
            raise


def create_scrapy_crawl_pipeline(document_store: OpenSearchDocumentStore) -> Pipeline:
    pipeline = Pipeline()
    crawler = ScrapyCrawlerComponent()
    presidio = PresidioAnonymizer()
    splitter = DocumentSplitter(split_by="word", split_length=150, split_overlap=50)
    embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
    writer = DocumentWriter(document_store, policy=DuplicatePolicy.SKIP)

    pipeline.add_component(instance=crawler, name="crawler")
    pipeline.add_component(instance=presidio, name="presidio_anonymizer")
    pipeline.add_component(instance=splitter, name="document_splitter")
    pipeline.add_component(instance=embedder, name="document_embedder")
    pipeline.add_component(instance=writer, name="document_writer")

    pipeline.connect("crawler", "presidio_anonymizer.documents")
    pipeline.connect("presidio_anonymizer", "document_splitter")
    pipeline.connect("document_splitter", "document_embedder")
    pipeline.connect("document_embedder", "document_writer")

    return pipeline
