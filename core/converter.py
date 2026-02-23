"""HTML → clean Markdown conversion with ad/nav stripping."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial

import httpx
import trafilatura
import truststore
from markdownify import markdownify

truststore.inject_into_ssl()


@dataclass(frozen=True, slots=True)
class ConversionResult:
    markdown: str
    title: str | None
    author: str | None
    date: str | None
    url: str


class ContentConverter:
    """Extracts article content from HTML and converts to clean Markdown.

    Uses trafilatura for main-content extraction (strips ads, nav, footers)
    and markdownify as a fallback for raw HTML→Markdown.
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def from_url(self, url: str) -> ConversionResult:
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True,
        ) as client:
            resp = await client.get(
                url, headers={"User-Agent": "Fairfetch/0.1 (+https://fairfetch.dev)"}
            )
            resp.raise_for_status()
            return await self.from_html(resp.text, url=url)

    async def from_html(self, html: str, *, url: str = "") -> ConversionResult:
        loop = asyncio.get_running_loop()
        extract = partial(self._extract, html, url)
        return await loop.run_in_executor(None, extract)

    @staticmethod
    def _extract(html: str, url: str) -> ConversionResult:
        metadata = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            include_links=True,
            url=url,
        )

        meta = trafilatura.extract(
            html,
            output_format="xml",
            url=url,
        )

        title: str | None = None
        author: str | None = None
        date: str | None = None

        if meta:
            import xml.etree.ElementTree as ET

            try:
                root = ET.fromstring(meta)
                title = root.get("title")
                author = root.get("author")
                date = root.get("date")
            except ET.ParseError:
                pass

        if metadata:
            markdown = metadata
        else:
            markdown = markdownify(html, strip=["script", "style", "nav", "footer", "header"])

        return ConversionResult(
            markdown=markdown.strip(),
            title=title,
            author=author,
            date=date,
            url=url,
        )
