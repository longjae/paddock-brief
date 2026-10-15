"""Links to FIA decision documents published for a race weekend."""

from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import httpx


FIA_DOCUMENTS_URL = "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14"
FIA_SEASONS = {2024: "season-2024-2043", 2025: "season-2025-2071", 2026: "season-2026-2072"}


def event_documents_url(season: int, name: str) -> str:
    season_path = FIA_SEASONS.get(season)
    if not season_path:
        return FIA_DOCUMENTS_URL
    return f"{FIA_DOCUMENTS_URL}/season/{season_path}/event/{quote(name, safe='')}"


class DecisionDocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.documents: list[dict[str, str]] = []
        self.in_row = False
        self.href = ""
        self.field = ""
        self.title_parts: list[str] = []
        self.published_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "li" and "document-row" in classes:
            self.in_row = True
            self.href = ""
            self.title_parts = []
            self.published_parts = []
        elif self.in_row and tag == "a":
            self.href = attributes.get("href") or ""
        elif self.in_row and tag == "div" and "title" in classes:
            self.field = "title"
        elif self.in_row and tag == "div" and "published" in classes:
            self.field = "published"

    def handle_data(self, data: str) -> None:
        if self.in_row and self.field == "title":
            self.title_parts.append(data)
        elif self.in_row and self.field == "published":
            self.published_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.field:
            self.field = ""
        if tag != "li" or not self.in_row:
            return
        title = " ".join(" ".join(self.title_parts).split())
        if self.href.startswith("/system/files/decision-document/") and any(
            word in title.lower() for word in ("decision", "infringement", "penalty")
        ):
            self.documents.append({
                "title": title,
                "publishedAt": " ".join(" ".join(self.published_parts).split()),
                "url": urljoin("https://www.fia.com", self.href),
            })
        self.in_row = False
        self.field = ""


async def fetch_decision_documents(season: int, name: str) -> dict[str, object]:
    source_url = event_documents_url(season, name)
    if season not in FIA_SEASONS:
        return {"sourceUrl": source_url, "documents": []}
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        response = await client.get(source_url)
        response.raise_for_status()
    parser = DecisionDocumentParser()
    parser.feed(response.text)
    return {"sourceUrl": source_url, "documents": parser.documents[:30]}
