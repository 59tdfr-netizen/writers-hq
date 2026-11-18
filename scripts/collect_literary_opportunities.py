#!/usr/bin/env python3
"""Collect open literary calls from vsekonkursy.ru and insert only future-deadline records."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://vsekonkursy.ru"
LIST_URL = BASE + "/tvorcheskie-konkursy/literaturnye-konkursy"
MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "8"))
USER_AGENT = "WritersHQOpportunityCollector/1.0 (+https://github.com/59tdfr-netizen/writers-hq)"
MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*(?:[./-]\s*)(\d{1,2})\s*(?:[./-]\s*)(20\d{2})(?!\d)"
    r"|(?<!\d)(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(20\d{2})(?!\d)",
    re.I,
)
DEADLINE_CONTEXT = re.compile(
    r"(?:дедлайн|срок(?: подачи)?|до какого числа|при[её]м заявок.{0,100}?до|"
    r"принимают.{0,80}?до|заявки.{0,80}?до|работы.{0,80}?до|при[её]м работ.{0,100}?до)"
    r"[^\n.!?]{0,100}",
    re.I,
)
EXPIRED_MARKER = re.compile(r"конкурс\s+прош[её]л|при[её]м\s+(?:заявок|работ)\s+заверш[её]н|архив", re.I)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/+$", "", parsed.path or "/")
    if path == "":
        path = "/"
    return urlunparse((parsed.scheme.lower() or "https", host, path, "", "", ""))


def normalize_title(title: str) -> str:
    # Mirrors the database trigger: lowercase, then remove whitespace and punctuation.
    lowered = title.strip().lower()
    return "".join(ch for ch in lowered if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


def parse_date(match: re.Match) -> date | None:
    try:
        if match.group(1):
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        else:
            day, month, year = int(match.group(4)), MONTHS[match.group(5).lower()], int(match.group(6))
        return date(year, month, day)
    except (ValueError, KeyError, TypeError):
        return None


def find_deadline(text: str, card_text: str) -> date | None:
    # Prefer dates explicitly attached to a deadline/admission phrase; do not confuse publication dates with deadlines.
    for source in (text, card_text):
        for context in DEADLINE_CONTEXT.findall(source):
            for match in DATE_RE.finditer(context):
                parsed = parse_date(match)
                if parsed:
                    return parsed
    # Listing summaries often say simply "Дедлайн 25 ноября 2026 года".
    for source in (card_text, text[:7000]):
        for line in re.split(r"[\n•|]+", source):
            if re.search(r"дедлайн|срок|при[её]м|принима|до\s+\d", line, re.I):
                for match in DATE_RE.finditer(line):
                    parsed = parse_date(match)
                    if parsed:
                        return parsed
    return None


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def collect_links(soup: BeautifulSoup) -> list[tuple[str, str, str]]:
    found = []
    seen = set()
    cards = soup.select("article, .post, .entry, .type-post")
    if not cards:
        cards = [a.parent.parent for a in soup.select("a[href]") if a.parent and a.parent.parent]
    for card in cards:
        text = clean_text(card.get_text(" ", strip=True))
        if not text or EXPIRED_MARKER.search(text):
            continue
        title_el = card.select_one("h1, h2, h3, .entry-title, .post-title")
        anchor = title_el.find("a", href=True) if title_el else None
        if anchor is None:
            for candidate in card.select("a[href]"):
                label = clean_text(candidate.get_text(" ", strip=True))
                href = candidate.get("href", "")
                if label and href and href not in ("#", "/") and "подробнее" not in label.lower():
                    anchor = candidate
                    break
        if anchor is None:
            continue
        title = clean_text(anchor.get_text(" ", strip=True))
        url = canonical_url(urljoin(BASE, anchor.get("href", "")))
        parsed = urlparse(url)
        if parsed.hostname not in ("vsekonkursy.ru", "www.vsekonkursy.ru") or url.rstrip("/") == LIST_URL.rstrip("/"):
            continue
        if len(title) < 8 or title.lower() in ("подробнее", "читать далее"):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append((title, url, text))
    return found


def extract_detail(url: str, list_text: str) -> dict | None:
    try:
        raw = fetch(url)
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"WARN detail fetch failed {url}: {exc}", file=sys.stderr)
        return None
    soup = BeautifulSoup(raw, "html.parser")
    page_text = clean_text(soup.get_text(" ", strip=True))
    if EXPIRED_MARKER.search(page_text[:5000]):
        return None
    deadline = find_deadline(page_text, list_text)
    if not deadline or deadline < date.today():
        return None

    title_el = soup.select_one("h1.entry-title, h1.post-title, article h1, main h1, h1")
    title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
    if not title:
        title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        title = re.sub(r"\s*[|–—-]\s*Все конкурсы.*$", "", title, flags=re.I)
    if len(title) < 8:
        return None

    organizer = ""
    organizer_match = re.search(r"Организатор\s*:\s*(.{3,180}?)(?:\s+(?:Описание|Условия|Этапы|Призы|Дедлайн)\b|$)", page_text, re.I)
    if organizer_match:
        organizer = clean_text(organizer_match.group(1)).strip(" .,:;")
    if not organizer:
        organizer = "Уточняется на странице конкурса"

    description = ""
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta and meta.get("content"):
        description = clean_text(meta["content"])
    if not description:
        content = soup.select_one("article .entry-content, .post-content, .entry-content, main")
        if content:
            for p in content.select("p"):
                candidate = clean_text(p.get_text(" ", strip=True))
                if len(candidate) > 70 and not re.search(r"организатор\s*:|дедлайн\s*:", candidate, re.I):
                    description = candidate
                    break
    if not description:
        description = "Открытый литературный конкурс. Подробные условия и требования — на странице организатора."
    description = description[:1200]

    submission_url = None
    for a in soup.select("a[href]"):
        label = clean_text(a.get_text(" ", strip=True)).lower()
        if re.search(r"подать заявку|отправить (?:работу|текст)|форма заявки|регистрация|заполнить анкету", label):
            candidate = canonical_url(urljoin(url, a["href"]))
            if urlparse(candidate).scheme in ("http", "https"):
                submission_url = candidate
                break

    text_for_tags = (title + " " + description).lower()
    genres = []
    if any(word in text_for_tags for word in ("фантаст", "фэнтези", "космоопер")):
        genres.extend(["Фантастика", "Фэнтези"] if "фэнтези" in text_for_tags else ["Фантастика"])
    if any(word in text_for_tags for word in ("пьес", "драматург")):
        genres.append("Драматургия")
    if any(word in text_for_tags for word in ("поэзи", "стихотвор")):
        genres.append("Поэзия")
    if any(word in text_for_tags for word in ("рассказ", "проз", "роман", "рукопис")):
        genres.append("Проза")
    genres = list(dict.fromkeys(genres))

    return {
        "title": title[:180],
        "organizer": organizer[:180],
        "summary": description,
        "genres": genres,
        "eligible_formats": [],
        "eligibility": "См. требования на странице конкурса",
        "fee_info": "Условия участия и возможный взнос — на странице конкурса",
        "deadline": deadline.isoformat(),
        "source_url": canonical_url(url),
        "submission_url": submission_url,
        "status": "open",
        "verified_at": date.today().isoformat(),
    }


def supabase_request(method: str, path: str, payload=None):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        # New Supabase sb_secret_* keys are opaque API keys, not JWTs.
        # Send them via apikey only; do not put them in Authorization: Bearer.
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=representation" if method == "POST" else "return=representation",
    }
    request = Request(base + "/rest/v1/" + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(body) if body else []
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 409:
            return 409, body
        raise RuntimeError(f"Supabase HTTP {exc.code}: {body[:500]}") from exc


def main():
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY GitHub Actions secrets")

    candidates = {}
    for page in range(1, MAX_PAGES + 1):
        page_url = LIST_URL if page == 1 else f"{LIST_URL}/page/{page}"
        try:
            soup = BeautifulSoup(fetch(page_url), "html.parser")
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            if page == 1:
                raise
            print(f"WARN list page skipped {page_url}: {exc}", file=sys.stderr)
            continue
        links = collect_links(soup)
        if not links and page > 1:
            print(f"INFO no more cards at page {page}; stopping")
            break
        for title, url, card_text in links:
            candidates[url] = (title, url, card_text)
        time.sleep(0.5)

    print(f"Found {len(candidates)} source-page candidates across up to {MAX_PAGES} pages")
    status, existing = supabase_request("GET", "writer_opportunities?select=title,source_url,deadline,dedupe_url_key,dedupe_title_deadline_key&limit=5000")
    if status != 200 or not isinstance(existing, list):
        raise RuntimeError("Could not load existing opportunity keys from Supabase")

    existing_urls = set()
    existing_title_deadlines = set()
    for row in existing:
        url_key = row.get("dedupe_url_key") or (canonical_url(row["source_url"]) if row.get("source_url") else "")
        if url_key:
            existing_urls.add(url_key)
        if row.get("title"):
            existing_title_deadlines.add(normalize_title(row["title"]) + "|" + (row.get("deadline") or "no-deadline"))

    dry_run = os.getenv("SCRAPER_DRY_RUN", "true").strip().lower() in ("1", "true", "yes", "on")
    print("Mode: DRY RUN — no database writes" if dry_run else "Mode: LIVE — database writes enabled")
    inserted = skipped = failed = 0
    would_insert = 0
    for _, (listed_title, url, card_text) in candidates.items():
        record = extract_detail(url, card_text)
        time.sleep(0.35)
        if not record:
            skipped += 1
            continue
        url_key = canonical_url(record["source_url"])
        title_deadline = normalize_title(record["title"]) + "|" + record["deadline"]
        if url_key in existing_urls or title_deadline in existing_title_deadlines:
            print(f"SKIP duplicate: {record['title']}")
            skipped += 1
            continue
        if dry_run:
            would_insert += 1
            print(f"WOULD INSERT: {record['title']} — deadline {record['deadline']}")
            continue
        try:
            code, result = supabase_request("POST", "writer_opportunities?on_conflict=dedupe_url_key", record)
            if code == 409 or (isinstance(result, str) and "duplicate key" in result.lower()) or (isinstance(result, list) and not result):
                print(f"SKIP database duplicate: {record['title']}")
                skipped += 1
                continue
            if code not in (200, 201):
                raise RuntimeError(f"unexpected Supabase status {code}")
            inserted += 1
            existing_urls.add(url_key)
            existing_title_deadlines.add(title_deadline)
            print(f"INSERTED: {record['title']} — deadline {record['deadline']}")
        except Exception as exc:
            failed += 1
            print(f"ERROR insert {record['title']}: {exc}", file=sys.stderr)

    print(f"Done: inserted={inserted}, would_insert={would_insert}, skipped={skipped}, failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
