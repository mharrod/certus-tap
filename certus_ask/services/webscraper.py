from __future__ import annotations

import logging
from dataclasses import dataclass

from bs4 import BeautifulSoup
from readability import Document as ReadabilityDocument

WEB_EXTRA_MESSAGE = "Web scraping features require the 'web' extra. Install with: pip install 'certus-tap[web]'"

# Import guards for optional web scraping dependencies
try:
    from requests_html import HTMLSession
except ImportError as exc:
    raise ImportError(WEB_EXTRA_MESSAGE) from exc

logger = logging.getLogger(__name__)


@dataclass
class WebPage:
    url: str
    title: str
    text: str
    html: str
    rendered: bool


def fetch_page(url: str, render: bool = False, timeout: int = 20, wait: float = 1.0) -> WebPage | None:
    session = HTMLSession()
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        if render:
            try:
                response.html.render(timeout=timeout, sleep=wait)
            except Exception as exc:  # pragma: no cover - external renderer variability
                logger.warning("Failed to render dynamic content for %s: %s", url, exc)
        html_content = response.html.html or response.text
        title, text = _extract_content(html_content)
        if not text.strip():
            logger.warning("No textual content extracted for %s", url)
            return None
        return WebPage(url=url, title=title, text=text, html=html_content, rendered=render)
    except Exception as exc:  # pragma: no cover - network variability
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None
    finally:
        session.close()


def _extract_content(html: str) -> tuple[str, str]:
    try:
        readability_doc = ReadabilityDocument(html)
        title = readability_doc.short_title() or "Untitled"
        cleaned_html = readability_doc.summary(html_partial=True)
        soup = BeautifulSoup(cleaned_html, "html.parser")
        text = soup.get_text("\n", strip=True)
        if text:
            return title, text
    except Exception as exc:  # pragma: no cover - fallback path
        logger.debug("Readability extraction failed, falling back to BeautifulSoup: %s", exc)

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.text.strip() if title_tag else "Untitled"
    text = soup.get_text("\n", strip=True)
    return title, text
