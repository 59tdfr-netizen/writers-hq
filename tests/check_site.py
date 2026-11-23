from html.parser import HTMLParser
from pathlib import Path
import subprocess
import re
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "index.html"
HTML = HTML_PATH.read_text(encoding="utf-8")


class InlineScriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs = dict(attrs)
        script_type = (attrs.get("type") or "").split(";")[0].strip().lower()
        if attrs.get("src") or script_type not in ("", "text/javascript", "application/javascript", "module"):
            self.current = None
            return
        self.current = []

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            source = "".join(self.current)
            if source.strip():
                self.scripts.append(source)
            self.current = None



def relative_luminance(hex_color):
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    channels = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first, second):
    luminance_a = relative_luminance(first)
    luminance_b = relative_luminance(second)
    lighter, darker = max(luminance_a, luminance_b), min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def final_css_token(name):
    values = re.findall(rf"{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{6}})", HTML)
    assert values, f"Missing CSS token {name}."
    return values[-1]


def main():
    assert '<html lang="ru">' in HTML, "Set the document language to Russian."
    assert '<meta name="description"' in HTML, "Missing SEO description."
    assert '<meta property="og:title"' in HTML, "Missing Open Graph title."
    assert "firstTab.focus({ preventScroll: true })" in HTML, "Opening the mobile navigation must move keyboard focus into the drawer."
    assert "event.key !== 'Tab'" in HTML and "nav.contains(document.activeElement)" in HTML, "The mobile navigation must keep keyboard focus inside the open drawer."
    assert "closeMenu(true)" in HTML, "Closing the mobile navigation must restore focus to its toggle."
    assert ".day.future{opacity:.48}" not in HTML, "Future calendar dates must remain readable."
    assert ".calendar .day.future{background:#f7efe4;color:var(--muted);opacity:1}" in HTML, "Future calendar dates must use the accessible muted text color."
    assert ".stat .label { color: var(--muted); }" in HTML, "Statistic labels must use the accessible muted text color."
    muted = final_css_token("--muted")
    for surface_name in ("--bg", "--paper"):
        surface = final_css_token(surface_name)
        assert contrast_ratio(muted, surface) >= 4.5, (
            f"Muted text contrast against {surface_name} must meet WCAG AA for normal text."
        )
    assert "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.1" in HTML, "Pin the Supabase SDK to an exact version."
    assert '<link rel="icon"' in HTML, "Missing favicon."
    assert 'resetPasswordForEmail' in HTML, "Missing password reset request."
    assert "event === 'PASSWORD_RECOVERY'" in HTML, "Missing password recovery screen."
    assert 'id="signupPassword" type="password" required minlength="8"' in HTML, "Signup password must be at least 8 characters."
    assert 'id="newPassword" type="password" minlength="8"' in HTML, "Password changes must require at least 8 characters."
    assert "if (password.length < 8)" in HTML, "Password updates must validate minimum length."
    assert "авторам, которые подписаны на меня" in HTML, "Explain who can see shared statistics."
    assert "strong.textContent=String(message??'')" in HTML, "Toast messages must be rendered as text, not HTML."
    assert "function avatarObjectPath(value)" in HTML, "Private avatar path validation is missing."
    assert "createSignedUrl(path, 3600)" in HTML, "Private avatars must use temporary signed URLs."
    assert "update({ avatar_url: path })" in HTML, "Store avatar object paths rather than expiring URLs."
    assert "getPublicUrl(path)" not in HTML, "Do not create public avatar URLs."
    preflight_avatar_migration = ROOT / "supabase" / "migrations" / "20261123024442_prepare_private_writer_avatars.sql"
    assert preflight_avatar_migration.is_file(), "Private avatar preflight migration is missing."
    preflight_avatar_sql = preflight_avatar_migration.read_text(encoding="utf-8").lower()
    assert "keeps the bucket public" in preflight_avatar_sql, "Preflight must not disable public URLs before the client rollout."
    assert "to authenticated" in preflight_avatar_sql and "using (bucket_id = 'writer-avatars')" in preflight_avatar_sql, "Preflight must let authenticated users request signed URLs for other avatars."
    final_avatar_migration = ROOT / "supabase" / "migrations" / "20261123030000_private_writer_avatars.sql"
    assert final_avatar_migration.is_file(), "Final private avatar migration is missing."
    final_avatar_sql = final_avatar_migration.read_text(encoding="utf-8").lower()
    assert "apply only after the signed-url client is deployed" in final_avatar_sql, "Final avatar migration must document rollout order."
    assert "set public = false" in final_avatar_sql, "Avatar storage bucket must be private after final migration."

    likes_migration = ROOT / "supabase" / "migrations" / "20261122083616_enrich_achievement_likes_feed.sql"
    assert likes_migration.is_file(), "Achievement likes feed migration is missing."
    likes_sql = likes_migration.read_text(encoding="utf-8")
    assert "liker_ids" in likes_sql and "like_count" in likes_sql, "Achievement feed must expose like counts and liker ids."
    assert "e.user_id = (select auth.uid())" in likes_sql, "Authors must see their own achievements after they receive likes."
    feed_migration = ROOT / "supabase" / "migrations" / "20261120161000_fix_achievement_feed_followers.sql"
    assert feed_migration.is_file(), "Achievement feed follower-direction migration is missing."
    feed_sql = feed_migration.read_text(encoding="utf-8")
    assert "wf.follower_id = (select auth.uid())" in feed_sql, "Achievement feed must select authors who follow the event author."
    assert "wf.followed_id = e.user_id" in feed_sql, "Achievement feed must only show events to the event author's followers."
    assert "s.show_stats_to_mutuals is true" in feed_sql, "Achievement feed must respect the author's explicit sharing consent."
    assert "security definer" in feed_sql.lower() and "set search_path to ''" in feed_sql.lower(), "Keep the feed function's security settings."
    grants_migration = ROOT / "supabase" / "migrations" / "20261123024140_fix_feed_privacy_and_rpc_grants.sql"
    assert grants_migration.is_file(), "RPC permission hardening migration is missing."
    grants_sql = grants_migration.read_text(encoding="utf-8").lower()
    assert "from public, anon, authenticated" in grants_sql, "RPC hardening must remove implicit PUBLIC and anonymous grants."
    assert "to authenticated" in grants_sql, "Client-facing RPCs must explicitly grant authenticated execution."
    assert "emailRedirectTo: window.location.origin + window.location.pathname" in HTML, "Email confirmation must follow the current site URL."
    assert 'id="confirmAdult" type="checkbox" required' in HTML, "Registration must require 18+ self-confirmation."
    assert "if (!$('confirmAdult').checked)" in HTML, "Registration handler must reject missing age confirmation."
    assert "emailRedirectTo: 'https://59tdfr-netizen.github.io/writers-hq/'" not in HTML, "Avoid hard-coded auth redirects."
    assert (ROOT / "assets" / "favicon.svg").is_file(), "Favicon file is missing."
    ET.parse(ROOT / "assets" / "favicon.svg")

    parser = InlineScriptExtractor()
    parser.feed(HTML)
    assert parser.scripts, "No inline JavaScript blocks found."

    with tempfile.TemporaryDirectory() as temp_dir:
        for index, source in enumerate(parser.scripts, start=1):
            script_path = Path(temp_dir) / f"inline-{index}.js"
            script_path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(script_path)],
                text=True,
                capture_output=True,
            )
            if result.returncode:
                raise SystemExit(
                    f"Inline script {index} has a JavaScript syntax error:\\n"
                    f"{result.stdout}{result.stderr}"
                )
    print(f"Site checks passed: metadata, favicon, {len(parser.scripts)} inline scripts.")


if __name__ == "__main__":
    main()
