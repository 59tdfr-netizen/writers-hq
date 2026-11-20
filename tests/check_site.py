from html.parser import HTMLParser
from pathlib import Path
import subprocess
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


def main():
    assert '<html lang="ru">' in HTML, "Set the document language to Russian."
    assert '<meta name="description"' in HTML, "Missing SEO description."
    assert '<meta property="og:title"' in HTML, "Missing Open Graph title."
    assert '<link rel="icon"' in HTML, "Missing favicon."
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
