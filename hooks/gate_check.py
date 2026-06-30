#!/usr/bin/env python3
"""PreToolUse hook: enforce startup gates.

Level 2 of the AI Agent Harness.
Blocks non-Read tools until all Tier 1 files are read.
Level 3 adds Tier 2 on-demand loading via keyword triggers.

Input: JSON on stdin with tool_name and tool_input fields.
Output: JSON on stdout to deny (with reason) or empty for allow.
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


def read_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: str, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2))


def deny(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def mark_file_read(sentinel: dict, manifest: dict, file_path: str) -> None:
    """Track that Claude has read a tier file."""
    for tier_key in ("tier1", "tier2"):
        for entry in manifest.get(tier_key, []):
            if entry.get("path") and file_path.endswith(os.path.basename(entry["path"])):
                if entry["name"] not in sentinel.get("completed_reads", []):
                    sentinel.setdefault("completed_reads", []).append(entry["name"])
                    write_json(SENTINEL, sentinel)
                return


def check_tier1_complete(sentinel: dict, manifest: dict) -> bool:
    tier1_names = {e["name"] for e in manifest.get("tier1", [])}
    read_names = set(sentinel.get("completed_reads", []))
    return tier1_names.issubset(read_names)


def check_tier2_triggers(tool_input: dict, manifest: dict) -> list[dict]:
    """Scan tool input for Tier 2 trigger keywords. Return matching tier2 entries."""
    gates = manifest.get("gates", {})
    if not gates.get("tier2_keyword_scan"):
        return []

    scan_fields = gates.get("keyword_scan_fields", ["command", "file_path", "prompt", "description"])
    max_chars = gates.get("keyword_scan_max_chars", 120)

    text_to_scan = ""
    for field in scan_fields:
        val = tool_input.get(field, "")
        if isinstance(val, str):
            text_to_scan += " " + val[:max_chars]
    text_lower = text_to_scan.lower()

    triggered = []
    for entry in manifest.get("tier2", []):
        if entry["name"] in _already_loaded(manifest):
            continue
        for trigger in entry.get("triggers", []):
            if trigger.lower() in text_lower:
                triggered.append(entry)
                break
    return triggered


def _already_loaded(manifest: dict) -> set[str]:
    sentinel = read_json(SENTINEL) or {}
    return set(sentinel.get("completed_reads", []))


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})

    sentinel = read_json(SENTINEL)
    manifest = read_json(MANIFEST)

    if not sentinel or not manifest:
        if tool_name == "Read":
            sys.exit(0)
        deny("Startup not initialized. Run SessionStart hook first.")
        return

    # Gate 1a: Always allow Read (needed to load tier files)
    # Gate 1b: Always allow git commits (don't block version control)
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if cmd.strip().startswith("git commit") or cmd.strip().startswith("git push"):
            sys.exit(0)

    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            mark_file_read(sentinel, manifest, file_path)

        # After marking, check if tier1 is now complete
        sentinel = read_json(SENTINEL) or sentinel
        if check_tier1_complete(sentinel, manifest) and sentinel.get("stage") != "complete":
            sentinel["stage"] = "complete"
            write_json(SENTINEL, sentinel)
        sys.exit(0)

    # Gate 2: Block non-Read tools until Tier 1 is complete
    gates = manifest.get("gates", {})
    if gates.get("block_until_tier1") and not check_tier1_complete(sentinel, manifest):
        tier1_names = {e["name"] for e in manifest.get("tier1", [])}
        read_names = set(sentinel.get("completed_reads", []))
        missing = tier1_names - read_names
        deny(f"Tier 1 startup incomplete. Still need to read: {', '.join(sorted(missing))}")
        return

    # Gate 3: Run cross-check once after tier1 completes
    if not sentinel.get("cross_check_done") and manifest.get("cross_check"):
        try:
            import subprocess
            result = subprocess.run(
                ["python3", os.path.join(os.path.dirname(__file__), "cross_check.py")],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip():
                sentinel = read_json(SENTINEL) or sentinel
        except Exception:
            pass

    # Gate 4: DB mode — warn about stale fact references (advisory)
    db_path = os.environ.get("AGENT_DB_PATH")
    if db_path and not sentinel.get("fact_check_done") and not db_path.startswith("postgresql"):
        try:
            import sqlite3
            db = sqlite3.connect(db_path, timeout=5)
            db.row_factory = sqlite3.Row
            stale = []
            rows = db.execute(
                "SELECT fact_key, fact_value, display_forms, file_name "
                "FROM system_facts sf JOIN fact_references fr ON sf.fact_key = fr.fact_key"
            ).fetchall()
            for row in rows:
                fpath = row["file_name"]
                if not os.path.exists(fpath):
                    continue
                content = Path(fpath).read_text().lower()
                forms = json.loads(row["display_forms"])
                if not any(f.lower() in content for f in forms):
                    stale.append(f"{row['fact_key']}={row['fact_value']} in {os.path.basename(fpath)}")
            db.close()
            sentinel["fact_check_done"] = True
            write_json(SENTINEL, sentinel)
            if stale:
                print(json.dumps({"hookSpecificOutput": {
                    "additionalContext": f"STALE FACTS ({len(stale)}): " + "; ".join(stale[:5])
                }}))
        except Exception:
            sentinel["fact_check_done"] = True
            write_json(SENTINEL, sentinel)

    # Gate 5: Check for Tier 2 triggers (advisory, not blocking)
    triggered = check_tier2_triggers(tool_input, manifest)
    if triggered:
        names = [t["name"] for t in triggered]
        sources = [t.get("source", "unknown") for t in triggered]
        msg = "Tier 2 files triggered — read before proceeding:\n"
        for name, source in zip(names, sources):
            msg += f"  - {name}: {source}\n"
        deny(msg)
        return

    sys.exit(0)


if __name__ == "__main__":
    main()
