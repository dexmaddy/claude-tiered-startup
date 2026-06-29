#!/usr/bin/env python3
"""Stop hook: enforce shutdown checks before session exit.

Level 4 of the Agentic AI Tiered Startup Architecture.
Blocks session exit (exit code 2 = retry) until configured checks pass.
After max retries, exits cleanly to avoid trapping the user.

Exit codes:
  0 — all checks pass, session can exit
  2 — checks failed, Claude should retry (fix the issues)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "default")
TMPDIR = tempfile.gettempdir()
MANIFEST = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
RETRY_COUNT_FILE = os.path.join(TMPDIR, f"stop-retries-{SESSION_ID}")


def read_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_retry_count() -> int:
    try:
        return int(Path(RETRY_COUNT_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def increment_retry_count() -> int:
    count = get_retry_count() + 1
    Path(RETRY_COUNT_FILE).write_text(str(count))
    return count


def check_clean_repos() -> tuple[bool, str]:
    """Check if git repos have uncommitted changes."""
    try:
        result = subprocess.run(
            "git status --porcelain", shell=True, capture_output=True, text=True, timeout=10
        )
        dirty = result.stdout.strip()
        if dirty:
            file_count = len(dirty.splitlines())
            return False, f"{file_count} uncommitted files"
        return True, "clean"
    except Exception as e:
        return False, str(e)


def check_transcript_saved() -> tuple[bool, str]:
    """Check if a transcript was saved today (customize path pattern)."""
    from datetime import date
    today = date.today().isoformat()
    transcript_dir = os.environ.get("TRANSCRIPT_DIR", ".")
    for f in Path(transcript_dir).glob(f"chat-{today}*.md"):
        return True, f.name
    return False, f"no transcript for {today}"


def main() -> None:
    manifest = read_json(MANIFEST)
    stop_config = (manifest or {}).get("stop", {})
    max_retries = stop_config.get("max_retries", 8)

    retries = get_retry_count()
    if retries >= max_retries:
        print(f"Max retries ({max_retries}) reached. Allowing exit.")
        sys.exit(0)

    failures = []

    if stop_config.get("require_clean_repos"):
        passed, detail = check_clean_repos()
        if not passed:
            failures.append(f"Repos not clean: {detail}")

    if stop_config.get("require_transcript"):
        passed, detail = check_transcript_saved()
        if not passed:
            failures.append(f"Transcript missing: {detail}")

    if failures:
        increment_retry_count()
        print("STOP BLOCKED — fix before exiting:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(2)

    print("All shutdown checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
