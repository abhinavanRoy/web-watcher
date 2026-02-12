from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://uni-freiburg.de/en/studies/during-your-studies/apis/"

STATE_DIR = Path(".state")
STATE_DIR.mkdir(exist_ok=True)
HASH_FILE = STATE_DIR / "current_social_events.sha256"
TEXT_FILE = STATE_DIR / "current_social_events.txt"

START_MARKER = "Current social events"
END_MARKER = "Past events"


def fetch_html(url: str) -> str:
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; APISWatcher/1.0)"},
    )
    r.raise_for_status()
    return r.text


def extract_current_social_events(html: str) -> str:
    """
    Extract the text between:
      'Current social events'  ...  'Past events'
    """
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text("\n", strip=True)

    if START_MARKER not in full_text or END_MARKER not in full_text:
        raise RuntimeError(
            f"Could not find markers. Needed '{START_MARKER}' and '{END_MARKER}'."
        )

    start = full_text.index(START_MARKER) + len(START_MARKER)
    end = full_text.index(END_MARKER, start)
    block = full_text[start:end].strip()

    # Normalize whitespace so tiny formatting changes don’t cause false alerts
    block = re.sub(r"[ \t]+\n", "\n", block)
    block = re.sub(r"\n{3,}", "\n\n", block).strip()
    return block


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def set_github_output(name: str, value: str) -> None:
    """
    Writes step outputs for GitHub Actions.
    """
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"{name}<<__EOF__\n{value}\n__EOF__\n")


def main() -> int:
    html = fetch_html(URL)
    block = extract_current_social_events(html)
    h = sha256(block)

    prev = read_text(HASH_FILE)

    changed = prev != h

    # Always update state so the next run compares against the latest
    write_text(HASH_FILE, h)
    write_text(TEXT_FILE, block)

    set_github_output("changed", "true" if changed else "false")
    set_github_output("url", URL)
    set_github_output("content", block)

    if changed:
        print("CHANGED: Current social events updated.")
        return 0

    print("No change.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Fail the workflow if parsing breaks (so you notice)
        print(f"ERROR: {e}")
        sys.exit(1)
