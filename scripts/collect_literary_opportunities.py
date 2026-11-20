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
SOURCES = [
    {"name": "Конкурсы.Пиши.про", "base_url": "https://konkursy.pishi.pro", "list_url": "https://konkursy.pishi.pro/", "pagination": "query"},
    {"name": "Печорин.net", "base_url": "https://pechorin.net", "list_url": "https://pechorin.net/competitions", "pagination": "query"},
    {"name": "ВсеКонкурсы", "base_url": BASE, "list_url": LIST_URL, "pagination": "path"},
]
MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "8"))
MAX_LIVE_INSERTS = min(10, max(1, int(os.getenv("SCRAPER_MAX_LIVE_INSERTS", "3"))))
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
    r"(?:дедлайн|срок(?: подачи)?|до какого числа|при[её]м заявок.{0,100}?до|окончание при[её]ма заявок|"
    r"принимают.{0,80}?до|заявки.{0,80}?до|работы.{0,80}?до|при[её]м работ.{0,100}?до)"
    r"[^\n.!?]{0,100}",
    re.I,
)
EXPIRED_MARKER = re.compile(r"конкурс\s+(?:уже\s+)?заверш[её]н|при[её]м\s+(?:заявок|работ)\s+заверш[её]н|при[её]м\s+заявок\s+закрыт|работы\s+не\s+принимаются|срок\s+подачи\s+ист[её]к", re.I)
GENERIC_ROUNDUP_TITLE = re.compile(r"^(?:все\s+)?конкурсы\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?$", re.I)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=12) as response:
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


def extract_eligibility(text: str) -> str:
    text = clean_text(text)
    patterns = (
        r"(?:к участию\s+(?:приглашаются|допускаются|принимаются)|участвовать\s+могут|участие\s+могут\s+принять)[^.!?]{0,240}[.!?]?",
        r"(?:возрастные ограничения|авторы в возрасте|участники в возрасте)[^.!?]{0,180}[.!?]?",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(0))[:300]
    return "Возрастные и территориальные условия не удалось надёжно извлечь автоматически; проверьте положение конкурса."


def extract_fee_info(text: str) -> str:
    text = clean_text(text)
    patterns = (
        r"(?:участие бесплатное|организационный взнос не предусмотрен|взнос не взимается|бесплатное участие)[^.!?]{0,140}[.!?]?",
        r"(?:стоимость участия|организационный взнос)\s*:\s*(?:платное|бесплатное|\d+[^.!?]{0,80})",
        r"участие платное[^.!?]{0,100}[.!?]?",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(0))[:220]
    return "Стоимость участия и возможный взнос не указаны в извлечённом тексте; проверьте условия у организатора."


def source_page_url(source: dict, page: int) -> str:
    if page <= 1:
        return source["list_url"]
    if source["pagination"] == "path":
        return source["list_url"].rstrip("/") + f"/page/{page}"
    separator = "&" if "?" in source["list_url"] else "?"
    return source["list_url"] + separator + f"page={page}"


def interleave_source_candidates(candidates_by_source: dict[str, list[tuple[str, str, str]]]) -> dict[str, tuple[str, str, str]]:
    """Round-robin candidates across sources so an insert cap cannot starve one source."""
    ordered = {}
    max_count = max((len(items) for items in candidates_by_source.values()), default=0)
    for index in range(max_count):
        for source in SOURCES:
            items = candidates_by_source.get(source["name"], [])
            if index < len(items):
                item = items[index]
                ordered[item[1]] = item
    return ordered


def collect_links(soup: BeautifulSoup, list_url: str = LIST_URL) -> list[tuple[str, str, str]]:
    found = []
    seen = set()
    host = (urlparse(list_url).hostname or "").lower()
    if host == "pechorin.net":
        # Process matching links directly: the page's card markup can change,
        # and walking up exactly two parents made otherwise valid cards disappear.
        cards = soup.select('a[href*="/competitions/view/"]')
    elif host == "konkursy.pishi.pro":
        cards = soup.select('a[href*="/vse-literaturnye-konkursy/"]')
    else:
        cards = soup.select("article, .post, .entry, .type-post")
        if not cards:
            cards = [a.parent.parent for a in soup.select("a[href]") if a.parent and a.parent.parent]
    for card in cards:
        direct_anchor = card if getattr(card, "name", None) == "a" else None
        context = direct_anchor.parent.parent if direct_anchor and direct_anchor.parent and direct_anchor.parent.parent else card
        text = clean_text(context.get_text(" ", strip=True))
        if not text or EXPIRED_MARKER.search(text):
            continue
        title_el = card.select_one("h1, h2, h3, .entry-title, .post-title") if not direct_anchor else None
        anchor = direct_anchor or (title_el.find("a", href=True) if title_el else None)
        if anchor is None and host in ("pechorin.net", "konkursy.pishi.pro"):
            selector = 'a[href*="/competitions/view/"]' if host == "pechorin.net" else 'a[href*="/vse-literaturnye-konkursy/"]'
            anchor = card.select_one(selector)
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
        if GENERIC_ROUNDUP_TITLE.fullmatch(title):
            print(f"SKIP roundup page (not an individual opportunity): {title}")
            continue
        source_base = f"{urlparse(list_url).scheme}://{urlparse(list_url).netloc}"
        url = canonical_url(urljoin(source_base, anchor.get("href", "")))
        parsed = urlparse(url)
        if parsed.hostname != host or url.rstrip("/") == canonical_url(list_url).rstrip("/"):
            continue
        if host == "konkursy.pishi.pro" and re.sub(r"/+$", "", parsed.path) == "/vse-literaturnye-konkursy":
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
    title_el = soup.select_one("h1.entry-title, h1.post-title, article h1, main h1, h1")
    page_title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
    article = soup.select_one("article .entry-content, article .post-content, .entry-content, .post-content, main")
    leading_content = clean_text(article.get_text(" ", strip=True))[:1800] if article else page_text[:1800]
    # Do not treat generic site navigation/footer words such as "архив" as evidence that a specific contest is closed.
    if EXPIRED_MARKER.search(page_title + " " + leading_content):
        print(f"SKIP explicitly closed/expired page: {url}")
        return None
    deadline = find_deadline(page_text, list_text)
    if not deadline:
        print(f"SKIP no reliable deadline found: {url}")
        return None
    if deadline < date.today():
        print(f"SKIP past deadline ({deadline.isoformat()}): {url}")
        return None

    title_el = soup.select_one("h1.entry-title, h1.post-title, article h1, main h1, h1")
    title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
    if not title:
        title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        title = re.sub(r"\s*[|–—-]\s*Все конкурсы.*$", "", title, flags=re.I)
    if len(title) < 8:
        print(f"SKIP missing/short title: {url}")
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
        if re.search(r"подать заявку|отправить (?:работу|текст)|форма заявки|электронная заявка|яндекс формы|ссылка на форму|ссылка на заявку|регистрация|заполнить анкету|перейти на сайт конкурса", label):
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
        "eligibility": extract_eligibility(leading_content + " " + page_text),
        "fee_info": extract_fee_info(leading_content + " " + page_text),
        "deadline": deadline.isoformat(),
        "source_url": canonical_url(url),
        "submission_url": submission_url,
        "status": "open",
        "verified_at": date.today().isoformat(),
    }


def supabase_request(method: str, path: str, payload=None):
    raw_base = os.environ["SUPABASE_URL"].strip().rstrip("/")
    parsed_base = urlparse(raw_base)
    # Accept either the canonical project URL or a URL that accidentally includes
    # the REST prefix; append /rest/v1 only once.
    if parsed_base.path.rstrip("/").endswith("/rest/v1"):
        clean_path = parsed_base.path.rstrip("/")[:-len("/rest/v1")]
        raw_base = urlunparse((parsed_base.scheme, parsed_base.netloc, clean_path, "", "", "")).rstrip("/")
    elif parsed_base.path not in ("", "/"):
        raise RuntimeError(
            "Invalid SUPABASE_URL path. Use the Supabase project base URL "
            "(https://<project-ref>.supabase.co), not a URL containing an API path."
        )
    base = raw_base
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
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY GitHub Actions secrets")

    # Fail early with a useful message if the GitHub secret contains only a project ref,
    # a URL without https://, or another value that urllib cannot use as an absolute URL.
    parsed_supabase_url = urlparse(supabase_url)
    if parsed_supabase_url.scheme not in ("https", "http") or not parsed_supabase_url.netloc:
        raise SystemExit(
            "Invalid SUPABASE_URL GitHub Actions secret: expected the full Supabase Project URL "
            "including https:// (for example, https://<project-ref>.supabase.co). "
            "Copy it from Supabase Project Settings → Data API / API. "
            "Do not print or share the secret value."
        )

    candidates_by_source = {}
    pages_checked = 0
    for source in SOURCES:
        consecutive_empty_pages = 0
        source_candidates = {}
        for page in range(1, MAX_PAGES + 1):
            page_url = source_page_url(source, page)
            try:
                soup = BeautifulSoup(fetch(page_url), "html.parser")
            except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
                if page == 1:
                    print(f"ERROR source={source['name']} first page failed: {exc}", file=sys.stderr)
                    break
                print(f"WARN list page skipped {page_url}: {exc}", file=sys.stderr)
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    break
                continue
            pages_checked += 1
            links = collect_links(soup, source["list_url"])
            print(f"INFO source={source['name']} page={page}: {len(links)} usable candidates")
            if not links and page > 1:
                consecutive_empty_pages += 1
                print(f"INFO source={source['name']} no usable cards on page {page}")
                if consecutive_empty_pages >= 2:
                    break
                time.sleep(0.5)
                continue
            consecutive_empty_pages = 0
            for title, url, card_text in links:
                source_candidates[url] = (title, url, card_text)
            time.sleep(0.5)
        candidates_by_source[source["name"]] = list(source_candidates.values())
        print(f"INFO source={source['name']} listing candidates={len(source_candidates)}")

    # Interleave sources so the live insert cap cannot starve any source.
    candidates = interleave_source_candidates(candidates_by_source)

    print(f"Found {len(candidates)} unique source-page candidates across {pages_checked} checked pages (limit {MAX_PAGES} per source)")
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

    # Safe by default: unset/empty values (including scheduled workflow inputs) must never enable writes.
    # Live mode requires an explicit false-like value such as "false", "0", "no", or "off".
    dry_run_setting = os.getenv("SCRAPER_DRY_RUN", "").strip().lower()
    dry_run = dry_run_setting not in ("0", "false", "no", "off")
    print("Mode: DRY RUN — no database writes" if dry_run else "Mode: LIVE — database writes enabled")
    inserted = skipped = failed = 0
    would_insert = 0
    live_attempts = 0
    max_dry_run_detail_checks = min(100, max(1, int(os.getenv("SCRAPER_MAX_DRY_RUN_DETAIL_CHECKS", "35"))))
    for candidate_index, (_, (listed_title, url, card_text)) in enumerate(candidates.items()):
        if dry_run and candidate_index >= max_dry_run_detail_checks:
            print(f"STOP dry-run detail check cap reached ({max_dry_run_detail_checks}); remaining candidates left for the next run")
            break
        if not dry_run and live_attempts >= MAX_LIVE_INSERTS:
            print(f"STOP live insert attempt cap reached ({MAX_LIVE_INSERTS}); remaining candidates left for a later run")
            break
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
            # Keep this dry-run's in-memory keys in sync so a matching item from
            # another source is reported as a duplicate, without writing to Supabase.
            existing_urls.add(url_key)
            existing_title_deadlines.add(title_deadline)
            continue
        try:
            # Let PostgREST/PostgreSQL honor every unique index. The dedupe indexes are
            # partial indexes (WHERE key IS NOT NULL), which cannot be targeted by the
            # simple on_conflict column parameter. Client-side checks above still avoid
            # known URL and title/deadline duplicates before attempting the insert.
            live_attempts += 1
            code, result = supabase_request("POST", "writer_opportunities", record)
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
