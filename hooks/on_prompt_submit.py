#!/usr/bin/env python3
"""UserPromptSubmit hook: startup gate + context reset detection + context health.

Level 2 of the Agentic AI Tiered Startup Architecture.
- Detects /clear (context reset) and invalidates sentinel to force re-startup.
- If Tier 1 is not complete, injects a blocking message telling the agent to read files first.
- After startup, tracks prompt count and warns at configurable thresholds.

Context reset detection (portable pattern):
  Claude Code: checks transcript length from hook input — after /clear, transcript is empty.
  Other tools: adapt detect_context_reset() to your tool's context-awareness API.
  Fallback: prompt counter mismatch (tool-agnostic, counter stored in sentinel).

Output: JSON with optional additionalContext to inject into the agent's context.
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
SENTINEL = os.path.join(TMPDIR, f"startup-complete-{SESSION_ID}.json")
MANIFEST = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
PROMPT_COUNT_FILE = os.path.join(TMPDIR, f"prompt-count-{SESSION_ID}")
INFRA_FAIL_SHOWN = os.path.join(TMPDIR, f"infra-fail-shown-{SESSION_ID}")

# Minimum prompt count before /clear detection activates.
# Prevents false positives on the first few prompts of a fresh session.
CLEAR_DETECT_MIN_PROMPTS = 5


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


def detect_context_reset(hook_input: dict | None) -> bool:
    """Detect if /clear (or equivalent) wiped the conversation context.

    The sentinel persists across /clear because it lives in /tmp, but the
    agent's context is empty. This mismatch means rules loaded during startup
    are gone and must be re-read.

    Detection signals (adapt for your tool):
    1. Claude Code: transcript from hook input is empty/short while our
       prompt counter is high — context was reset mid-session.
    2. Tool-agnostic fallback: if prompt_count > threshold but sentinel
       has no prompt_count field, sentinel predates this feature — skip.

    Returns True if context was likely reset and sentinel should be invalidated.
    """
    sentinel = read_json(SENTINEL)
    if not sentinel or sentinel.get("stage") != "complete":
        return False

    prompt_count = get_prompt_count()
    if prompt_count < CLEAR_DETECT_MIN_PROMPTS:
        return False

    # Signal 1 (Claude Code): transcript length from hook input
    if hook_input:
        transcript = hook_input.get("transcript", [])
        user_messages = [m for m in transcript
                         if isinstance(m, dict) and m.get("role") == "user"]
        if len(user_messages) <= 1:
            return True

    # Signal 2 (tool-agnostic fallback): extend here for other tools.
    # Example: check elapsed time since last activity, or query your
    # tool's API for context/conversation state.

    return False


def invalidate_for_restart() -> None:
    """Delete sentinel and related state files to force full re-startup."""
    for path in (SENTINEL, PROMPT_COUNT_FILE, INFRA_FAIL_SHOWN):
        try:
            os.remove(path)
        except OSError:
            pass


def re_trigger_startup() -> None:
    """Re-run the SessionStart hook to regenerate manifest and tier files."""
    hook_dir = Path(__file__).resolve().parent
    startup_script = hook_dir / "on_session_start.py"
    if startup_script.exists():
        try:
            subprocess.run([sys.executable, str(startup_script)],
                           capture_output=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            pass


def check_infra_fails(manifest: dict) -> list[str]:
    """Parse the infra report for [FAIL] lines."""
    for entry in manifest.get("tier1", []):
        if entry.get("name") == "infra-report" or entry.get("type") == "checks":
            report_path = entry.get("path", "")
            if report_path and os.path.exists(report_path):
                fails = []
                with open(report_path) as f:
                    for line in f:
                        if "[FAIL]" in line:
                            fails.append(line.strip().lstrip("- "))
                return fails
    return []


def main() -> None:
    # Read hook input from stdin (Claude Code passes transcript here)
    hook_input = None
    try:
        raw = sys.stdin.read()
        if raw.strip():
            hook_input = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        pass

    # Detect /clear BEFORE checking startup — must invalidate sentinel first
    if detect_context_reset(hook_input):
        invalidate_for_restart()
        re_trigger_startup()

        gate_msg = (
            "CONTEXT RESET DETECTED (/clear or equivalent).\n"
            "Sentinel invalidated and startup re-triggered.\n"
            "You MUST read all Tier 1 files BEFORE responding to the user.\n"
            "Check the SessionStart hook output for the manifest path, "
            "then read every Tier 1 file listed in it."
        )
        output = {"hookSpecificOutput": {"additionalContext": gate_msg}}
        print(json.dumps(output))
        sys.exit(0)

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

    # Startup complete — check for infra FAILs (first prompt only)
    messages = []

    if not os.path.exists(INFRA_FAIL_SHOWN):
        fails = check_infra_fails(manifest)
        if fails:
            fail_list = "\n".join(f"  - {f}" for f in fails)
            messages.append(
                f"ACTION REQUIRED: {len(fails)} infrastructure FAIL(s) detected. "
                "You MUST fix these BEFORE responding to the user:\n"
                f"{fail_list}\n"
                "Fix each one (commit, resolve, or explain why acceptable), "
                "then confirm 0 FAIL before proceeding."
            )
        Path(INFRA_FAIL_SHOWN).write_text("1")

    # Track prompt count and warn at thresholds
    count = increment_prompt_count()
    gates = manifest.get("gates", {}) if manifest else {}
    thresholds = gates.get("prompt_health_warnings", [40, 60, 80])

    for threshold in thresholds:
        if count == threshold:
            messages.append(
                f"CONTEXT HEALTH: {count} prompts this session. "
                "Performance may be degrading. Consider saving state and starting fresh with /clear. "
                "Use subagents (Agent tool) for heavy operations."
            )
            break

    if messages:
        combined = "\n".join(messages)
        output = {"hookSpecificOutput": {"additionalContext": combined}}
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
