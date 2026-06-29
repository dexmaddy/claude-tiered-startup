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

    # Self-Verification: if infrastructure files were edited after the last check, require re-run
    if stop_config.get("require_self_verification", True):
        check_file = os.path.join(TMPDIR, f"last-infra-check-{SESSION_ID}")
        fix_file = os.path.join(TMPDIR, f"last-infra-fix-{SESSION_ID}")
        try:
            last_check_time = Path(check_file).stat().st_mtime if Path(check_file).exists() else 0
            last_fix_time = Path(fix_file).stat().st_mtime if Path(fix_file).exists() else 0
            if last_fix_time > last_check_time and last_fix_time > 0:
                fix_detail = Path(fix_file).read_text().strip() if Path(fix_file).exists() else "unknown"
                failures.append(
                    f"Self-Verification: '{fix_detail}' was edited after last infra check. "
                    "Re-run verification before stopping."
                )
        except Exception:
            pass

    if stop_config.get("require_clean_repos"):
        passed, detail = check_clean_repos()
        if not passed:
            failures.append(f"Repos not clean: {detail}")

    if stop_config.get("require_transcript"):
        passed, detail = check_transcript_saved()
        if not passed:
            failures.append(f"Transcript missing: {detail}")

    # Audit checks: run full audit if configured
    if stop_config.get("require_audit_pass"):
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from audit import run_audit
            checks_path = stop_config.get("audit_checks_path")
            summary = run_audit(checks_path=checks_path, critical_only=True)
            if not summary["all_critical_pass"]:
                failed_names = [r["name"] for r in summary["results"]
                                if r["status"] == "FAIL" and r.get("critical")]
                failures.append(
                    f"Audit: {summary['critical_failed']} critical check(s) failed: "
                    + ", ".join(failed_names)
                )
        except ImportError:
            pass
        except Exception as e:
            failures.append(f"Audit runner error: {e}")

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
