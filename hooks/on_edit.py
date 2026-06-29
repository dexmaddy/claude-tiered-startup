#!/usr/bin/env python3
"""PostToolUse hook: actions after file writes.

Level 4 of the Agentic AI Tiered Startup Architecture.
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

    # --- CUSTOMIZE BELOW ---

    # Example: sync memory files to backup locations
    # SYNC_DIRS = ["/path/to/backup1", "/path/to/backup2"]
    # if "/memory/" in file_path:
    #     failures = sync_file(file_path, SYNC_DIRS)
    #     if failures:
    #         print(json.dumps({"hookSpecificOutput": {
    #             "additionalContext": f"SYNC FAILED: {'; '.join(failures)}"
    #         }}))
    #         sys.exit(0)

    # Example: periodic save reminder
    if count > 0 and count % SAVE_REMINDER_INTERVAL == 0:
        print(json.dumps({"hookSpecificOutput": {
            "additionalContext": f"SAVE REMINDER: {count} edits this session. Consider committing and pushing."
        }}))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
