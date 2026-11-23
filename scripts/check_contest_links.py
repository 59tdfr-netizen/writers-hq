#!/usr/bin/env python3
"""Check a bounded sample of upcoming contest links without hammering source sites."""
import json, os, sys, time
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LIMIT = min(25, max(1, int(os.getenv("LINK_CHECK_LIMIT", "25"))))
AGENT = "WritersHQLinkHealth/1.0 (+https://github.com/59tdfr-netizen/writers-hq)"

def check(url):
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,*/*;q=0.8"}, method="HEAD")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status
    except HTTPError as exc:
        if exc.code in (405, 501):
            try:
                request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,*/*;q=0.8"}, method="GET")
                with urlopen(request, timeout=10) as response:
                    return response.status
            except HTTPError as retry:
                return retry.code
            except (URLError, TimeoutError):
                return None
        return exc.code
    except (URLError, TimeoutError):
        return None

def main():
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print("ERROR: required Supabase secrets are missing; values are not printed.", file=sys.stderr)
        return 2
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    endpoint = f"{base}/rest/v1/writer_opportunities?select=title,source_url,deadline&source_url=not.is.null&deadline=gte.{today}&order=deadline.asc&limit={LIMIT}"
    request = Request(endpoint, headers={"apikey": key, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            records = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        print(f"ERROR: Supabase query failed with HTTP {exc.code}; response details suppressed.", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: Supabase query failed ({type(exc).__name__}); response details suppressed.", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("ERROR: unexpected Supabase response shape.", file=sys.stderr)
        return 2
    last_host = defaultdict(float)
    broken, warnings = [], []
    for row in records:
        title = str(row.get("title") or "(без названия)")[:100]
        raw = str(row.get("source_url") or "")
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            broken.append((title, "invalid URL", ""))
            continue
        host = parsed.hostname
        pause = 1.0 - (time.monotonic() - last_host[host])
        if pause > 0: time.sleep(pause)
        status = check(raw)
        last_host[host] = time.monotonic()
        if status in (404, 410):
            broken.append((title, str(status), host))
            print(f"BROKEN | {title} | {status} | {host}")
        elif status is None or status >= 400:
            warnings.append((title, str(status or "network"), host))
            print(f"WARN | {title} | {status or 'network error'} | {host}")
        else:
            print(f"OK | {title} | {status} | {host}")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Проверка ссылок конкурсов\n\n")
            out.write(f"Проверено: **{len(records)}**; 404/410: **{len(broken)}**; требуют ручной проверки: **{len(warnings)}**.\n")
            for title, status, host in broken:
                out.write(f"\n- Битая ссылка: {title} — {status} ({host})")
            for title, status, host in warnings:
                out.write(f"\n- Предупреждение: {title} — {status} ({host})")
    return 1 if broken else 0

if __name__ == "__main__":
    raise SystemExit(main())
