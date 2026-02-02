import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OlympiadParser/1.0; +https://example.org)"
}


def _fetch_html(url, timeout=10):
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def _extract_title(soup):
    title = soup.find("h1")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return "Новость олимпиады"


def _extract_date(text):
    if not text:
        return None

    date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", text)
    if date_match:
        try:
            parsed = datetime.strptime(date_match.group(1), "%d.%m.%Y")
            return parsed.strftime("%d %b %Y")
        except ValueError:
            return date_match.group(1)

    month_match = re.search(
        r"(\d{1,2})\s+(январ[ья]|феврал[ья]|марта|апрел[ья]|мая|июн[ья]|июл[ья]|"
        r"август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\s+(\d{4})",
        text,
        re.IGNORECASE
    )
    if month_match:
        return f"{month_match.group(1)} {month_match.group(2)} {month_match.group(3)}"

    return None


def _build_news_item(url, subject, fallback_summary):
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    text = soup.get_text(" ", strip=True)
    date = _extract_date(text) or "2025–2026"
    return {
        "title": title,
        "subject": subject,
        "date": date,
        "summary": fallback_summary,
        "source": url
    }


def fetch_olympiad_news():
    news_sources = [
        {
            "url": "https://olymp-online.mipt.ru/",
            "subject": "Математика",
            "summary": "Обновления Физтех-олимпиады: регистрация, этапы и результаты."
        },
        {
            "url": "https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee",
            "subject": "Физика",
            "summary": "График заключительного этапа олимпиады «Шаг в будущее»."
        },
        {
            "url": "https://olymp.mephi.ru/rosatom/about",
            "subject": "Математика",
            "summary": "Объявления и материалы олимпиады «Росатом»."
        },
        {
            "url": "https://olymp.msu.ru/rus/page/main/29/page/grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026",
            "subject": "Информатика",
            "summary": "Расписание заключительного этапа Ломоносовской олимпиады 2025–2026."
        }
    ]

    news = []
    for source in news_sources:
        try:
            news.append(
                _build_news_item(
                    source["url"],
                    source["subject"],
                    source["summary"]
                )
            )
        except requests.RequestException:
            news.append(
                {
                    "title": "Обновление недоступно",
                    "subject": source["subject"],
                    "date": "2025–2026",
                    "summary": source["summary"],
                    "source": source["url"]
                }
            )
    return news


def fetch_olympiad_calendar():
    calendar_sources = [
        {
            "name": "Физтех-олимпиада",
            "subject": "Математика",
            "stage": "Актуальный график",
            "format": "Онлайн",
            "link": "https://olymp-online.mipt.ru/"
        },
        {
            "name": "ШВБ",
            "subject": "Математика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee"
        },
        {
            "name": "ШВБ",
            "subject": "Физика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee"
        },
        {
            "name": "Олимпиада “Росатом”",
            "subject": "Математика",
            "stage": "График 2025–2026",
            "format": "Очно",
            "link": "https://olymp.mephi.ru/rosatom/about"
        },
        {
            "name": "Олимпиада “Ломоносов”",
            "subject": "Физика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.msu.ru/rus/page/main/29/page/grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026"
        },
        {
            "name": "ШВБ",
            "subject": "Информатика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee"
        },
        {
            "name": "Олимпиада “Росатом”",
            "subject": "Физика",
            "stage": "График 2025–2026",
            "format": "Очно",
            "link": "https://olymp.mephi.ru/rosatom/about"
        },
        {
            "name": "Олимпиада “Ломоносов”",
            "subject": "Математика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.msu.ru/rus/page/main/29/page/grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026"
        },
        {
            "name": "Олимпиада “Ломоносов”",
            "subject": "Информатика",
            "stage": "Заключительный этап",
            "format": "Очно",
            "link": "https://olymp.msu.ru/rus/page/main/29/page/grafik-provedeniya-zakluchitelnogo-ehtapa-2025-2026"
        }
    ]

    calendar = []
    for source in calendar_sources:
        try:
            html = _fetch_html(source["link"])
            soup = BeautifulSoup(html, "html.parser")
            date = _extract_date(soup.get_text(" ", strip=True)) or "2025–2026"
        except requests.RequestException:
            date = "2025–2026"

        calendar.append(
            {
                "name": source["name"],
                "subject": source["subject"],
                "stage": source["stage"],
                "date": date,
                "format": source["format"],
                "link": source["link"]
            }
        )

    return calendar