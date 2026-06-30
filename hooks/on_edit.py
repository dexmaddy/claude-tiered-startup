#!/usr/bin/env python3
"""PostToolUse hook: actions after file writes.

Level 4 of the AI Agent Harness.
Runs after every Write/Edit tool call. Extend with your own post-write actions.

Common uses:
  - Sync important files to backup locations
  - Detect stale references after edits
  - Log edit activity for session summaries
  - Periodic save reminders

Input: JSON on stdin with tool_name, tool_input (file_path), tool_result.
Output: JSON on stdout with optional additionalContext.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "default")
TMPDIR = tempfile.gettempdir()
EDIT_COUNT_FILE = os.path.join(TMPDIR, f"edit-count-{SESSION_ID}")
SAVE_REMINDER_INTERVAL = 15  # remind every N edits


def get_edit_count() -> int:
    try:
        return int(Path(EDIT_COUNT_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def increment_edit_count() -> int:
    count = get_edit_count() + 1
    Path(EDIT_COUNT_FILE).write_text(str(count))
    return count


def sync_file(file_path: str, destinations: list[str]) -> list[str]:
    """Copy a file to multiple backup destinations. Returns list of failures."""
    import shutil
    failures = []
    for dest in destinations:
        dest_path = os.path.join(dest, os.path.basename(file_path))
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            failures.append(f"{dest}: {e}")
    return failures


def check_rule_zero(file_path: str, consolidated_files: dict[str, list[str]]) -> list[str]:
    """Rule Zero enforcement: detect if edited file's content belongs in a consolidated file.

    consolidated_files: mapping of glob pattern -> base keywords.
    Configure via startup-config.yaml 'consolidated_files' key.
    """
    import glob as _glob
    import re as _re

    if not file_path or not os.path.isfile(file_path):
        return []

    try:
        content = Path(file_path).read_text().lower()
    except Exception:
        return []

    if len(content) < 50:
        return []

    basename = os.path.basename(file_path)
    parent_dir = os.path.dirname(file_path)
    warnings = []

    for pattern, base_keywords in consolidated_files.items():
        matches = _glob.glob(os.path.join(parent_dir, pattern))
        for fpath in matches:
            fname = os.path.basename(fpath)
            if fname == basename:
                continue
            try:
                text = Path(fpath).read_text()
                headings = _re.findall(r'^##?\s+(.+)', text, _re.MULTILINE)
                keywords = base_keywords + [h.strip().lower() for h in headings[:10]]
            except Exception:
                keywords = base_keywords

            hits = [kw for kw in keywords if kw in content]
            if len(hits) >= 3:
                warnings.append(
                    f"RULE ZERO: '{basename}' has keywords matching '{fname}' "
                    f"({', '.join(hits[:4])}). Should this content go there instead?"
                )

    return warnings


# Default consolidated files for Rule Zero — override via startup-config.yaml
DEFAULT_CONSOLIDATED_FILES = {
    "MEMORY.md": ["memory", "pointer", "reference", "project state"],
    "*.md": ["feedback", "project", "reference", "architecture"],
}


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})

    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    count = increment_edit_count()
    messages = []

    # Rule Zero: detect scattered information
    consolidated = DEFAULT_CONSOLIDATED_FILES
    config_path = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
    try:
        manifest = json.loads(Path(config_path).read_text())
        consolidated = manifest.get("rule_zero", {}).get("consolidated_files", consolidated)
    except Exception:
        pass

    rz_warnings = check_rule_zero(file_path, consolidated)
    messages.extend(rz_warnings)

    # Sync memory files to backup locations
    # SYNC_DIRS = ["/path/to/backup1", "/path/to/backup2"]
    # if "/memory/" in file_path:
    #     failures = sync_file(file_path, SYNC_DIRS)
    #     if failures:
    #         messages.append(f"SYNC FAILED: {'; '.join(failures)}")

    # DB mode: log edit to rule_log table
    db_path = os.environ.get("AGENT_DB_PATH")
    if db_path and not db_path.startswith("postgresql"):
        try:
            import sqlite3
            db = sqlite3.connect(db_path, timeout=5)
            db.execute(
                "INSERT INTO rule_log (event_type, result, details, session_id) "
                "VALUES ('edit', 'logged', ?, ?)",
                (f"Edited: {os.path.basename(file_path)}", SESSION_ID),
            )
            db.commit()
            db.close()
        except Exception:
            pass

    # Periodic save reminder
    if count > 0 and count % SAVE_REMINDER_INTERVAL == 0:
        messages.append(f"SAVE REMINDER: {count} edits this session. Consider committing and pushing.")

    if messages:
        print(json.dumps({"hookSpecificOutput": {
            "additionalContext": "\n".join(messages)
        }}))

    sys.exit(0)


if __name__ == "__main__":
    main()
