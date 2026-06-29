#!/usr/bin/env python3
"""UserPromptSubmit hook: startup gate + context health warnings.

Level 2 of the Agentic AI Tiered Startup Architecture.
- If Tier 1 is not complete, injects a blocking message telling Claude to read files first.
- After startup, tracks prompt count and warns at configurable thresholds.

Output: JSON with optional additionalContext to inject into Claude's context.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "default")
TMPDIR = tempfile.gettempdir()
SENTINEL = os.path.join(TMPDIR, f"startup-complete-{SESSION_ID}.json")
MANIFEST = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
PROMPT_COUNT_FILE = os.path.join(TMPDIR, f"prompt-count-{SESSION_ID}")


def read_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_prompt_count() -> int:
    try:
        return int(Path(PROMPT_COUNT_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def increment_prompt_count() -> int:
    count = get_prompt_count() + 1
    Path(PROMPT_COUNT_FILE).write_text(str(count))
    return count


def main() -> None:
    sentinel = read_json(SENTINEL)
    manifest = read_json(MANIFEST)

    # No startup initialized — let SessionStart hook handle it
    if not sentinel or not manifest:
        sys.exit(0)

    # Startup incomplete — inject blocking gate message
    if sentinel.get("stage") != "complete":
        tier1_files = manifest.get("tier1", [])
        read_names = set(sentinel.get("completed_reads", []))
        missing = [e for e in tier1_files if e["name"] not in read_names]

        file_list = "\n".join(f"  - {e['path']}" for e in missing)
        gate_msg = (
            f"STARTUP INCOMPLETE: {len(missing)} Tier 1 files still unread.\n"
            f"Read these files BEFORE responding to the user:\n{file_list}\n"
            "Do NOT skip startup. Do NOT explain what startup does — just do it."
        )
        output = {"hookSpecificOutput": {"additionalContext": gate_msg}}
        print(json.dumps(output))
        sys.exit(0)

    # Startup complete — track prompt count and warn at thresholds
    count = increment_prompt_count()
    gates = manifest.get("gates", {})
    thresholds = gates.get("prompt_health_warnings", [40, 60, 80])

    for threshold in thresholds:
        if count == threshold:
            warn_msg = (
                f"CONTEXT HEALTH: {count} prompts this session. "
                "Performance may be degrading. Consider saving state and starting fresh with /clear. "
                "Use subagents (Agent tool) for heavy operations."
            )
            output = {"hookSpecificOutput": {"additionalContext": warn_msg}}
            print(json.dumps(output))
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
