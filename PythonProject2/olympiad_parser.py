import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 15
CACHE_TTL_SECONDS = 60 * 60

NEWS_SOURCES = [
    {
        "label": "MIPT Olymp Online",
        "url": "https://olymp-online.mipt.ru/",
    },
    {
        "label": "BMSTU News",
        "url": "https://olymp.bmstu.ru/ru/news/2025/12/25/"
        "raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee",
    },
    {
        "label": "MEPhI Rosatom",
        "url": "https://olymp.mephi.ru/rosatom/about",
    },
    {
        "label": "MSU Olymp Schedule",
        "url": "https://olymp.msu.ru/rus/page/main/29/page/"
        "grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026",
    },
]

CALENDAR_SOURCES = [
    {
        "name": "MIPT Olymp",
        "subject": "Math",
        "stage": "Schedule",
        "format": "Online",
        "link": "https://olymp-online.mipt.ru/",
    },
    {
        "name": "BMSTU Step Into the Future",
        "subject": "Mixed",
        "stage": "Final stage",
        "format": "Onsite",
        "link": "https://olymp.bmstu.ru/ru/news/2025/12/25/"
        "raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee",
    },
    {
        "name": "Rosatom Olympiad",
        "subject": "Mixed",
        "stage": "Schedule 2025-2026",
        "format": "Onsite",
        "link": "https://olymp.mephi.ru/rosatom/about",
    },
    {
        "name": "MSU Lomonosov Olympiad",
        "subject": "Mixed",
        "stage": "Final stage",
        "format": "Onsite",
        "link": "https://olymp.msu.ru/rus/page/main/29/page/"
        "grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026",
    },
]

_CACHE: Dict[str, Dict[str, object]] = {
    "news": {"ts": 0.0, "items": []},
    "calendar": {"ts": 0.0, "items": []},
}


def fetch_olympiad_news() -> List[Dict[str, str]]:
    return _fetch_cached("news", _build_news)


def fetch_olympiad_calendar() -> List[Dict[str, str]]:
    return _fetch_cached("calendar", _build_calendar)


def _fetch_cached(kind: str, builder) -> List[Dict[str, str]]:
    now = time.time()
    bucket = _CACHE[kind]
    items = bucket["items"]
    if items and now - bucket["ts"] < CACHE_TTL_SECONDS:
        return list(items)

    items = builder()
    bucket["items"] = items
    bucket["ts"] = now
    return list(items)


def _build_news() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        for source in NEWS_SOURCES:
            try:
                html = _fetch_html(session, source["url"])
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(" ", strip=True)
                title = _extract_title(soup) or source["label"]
                summary = _extract_summary(soup)
                date_text = _extract_date(text, source["url"]) or "2025-2026"
                items.append(
                    {
                        "title": title,
                        "subject": source["label"],
                        "date": date_text,
                        "summary": summary or "See the source for details.",
                        "source": source["url"],
                    }
                )
            except requests.RequestException:
                items.append(
                    {
                        "title": "Update not available",
                        "subject": source["label"],
                        "date": "2025-2026",
                        "summary": "See the source for details.",
                        "source": source["url"],
                    }
                )
    return items


def _build_calendar() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})
        for source in CALENDAR_SOURCES:
            try:
                html = _fetch_html(session, source["link"])
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(" ", strip=True)
                date_text = _extract_date(text, source["link"]) or "2025-2026"
            except requests.RequestException:
                date_text = "2025-2026"

            items.append(
                {
                    "name": source["name"],
                    "subject": source["subject"],
                    "stage": source["stage"],
                    "date": date_text,
                    "format": source["format"],
                    "link": source["link"],
                }
            )
    return items


def _fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    for tag in ("h1", "title"):
        node = soup.find(tag)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None


def _extract_summary(soup: BeautifulSoup) -> Optional[str]:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text and len(text) >= 60:
            return text
    return None


def _extract_date(text: str, url: Optional[str] = None) -> Optional[str]:
    if text:
        match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text)
        if match:
            day, month, year = match.group(1), match.group(2), match.group(3)
            year = f"20{year}" if len(year) == 2 else year
            return f"{int(day):02d}.{int(month):02d}.{year}"

        match = re.search(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", text)
        if match:
            year, month, day = match.group(1), match.group(2), match.group(3)
            return f"{int(day):02d}.{int(month):02d}.{year}"

    if url:
        match = re.search(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", url)
        if match:
            year, month, day = match.group(1), match.group(2), match.group(3)
            return f"{int(day):02d}.{int(month):02d}.{year}"

    return None
