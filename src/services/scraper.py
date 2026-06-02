"""
URL metadata scraper service.

Provides an async function that fetches a web page and extracts
its title, meta description, and favicon URL.

All failures are swallowed gracefully — the caller receives ``None``
for any element that could not be extracted.
"""

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


@dataclass
class ScrapedMetadata:
    """Container for metadata extracted from a URL."""

    title: str | None = None
    description: str | None = None
    favicon_url: str | None = None


async def scrape_url_metadata(url: str) -> ScrapedMetadata:
    """
    Fetch a URL and extract page metadata.

    Returns a ``ScrapedMetadata`` instance with whatever could be
    extracted.  Never raises — network errors and parse failures
    result in ``None`` fields.
    """
    result = ScrapedMetadata()

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; PersonalOS/0.1; "
                    "+https://github.com/personal-os)"
                )
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        return result

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return result

    # ── Title ───────────────────────────────────────────────────────────
    try:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            result.title = title_tag.string.strip()
    except Exception:
        pass

    # ── Meta description ────────────────────────────────────────────────
    try:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            content = meta_desc.get("content")
            if isinstance(content, list):
                content = content[0] if content else ""
            if content:
                result.description = content.strip()
    except Exception:
        pass

    # ── Favicon ─────────────────────────────────────────────────────────
    try:
        icon_link = soup.find(
            "link", rel=lambda r: r and "icon" in (r if isinstance(r, list) else [r])
        )
        if icon_link:
            href = icon_link.get("href")
            if isinstance(href, list):
                href = href[0] if href else ""
            if href:
                result.favicon_url = urljoin(url, href)
            else:
                result.favicon_url = urljoin(url, "/favicon.ico")
        else:
            # Fallback: try /favicon.ico at the domain root
            result.favicon_url = urljoin(url, "/favicon.ico")
    except Exception:
        pass

    return result
