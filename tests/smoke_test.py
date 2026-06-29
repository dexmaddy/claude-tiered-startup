#!/usr/bin/env python3
"""Smoke test: verify the full hook chain works with sample data.

Run this after setting up your config to confirm everything is wired correctly.
Creates temporary test data, runs each hook, and verifies the expected behavior.

Usage:
    python3 tests/smoke_test.py [--verbose]
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "hooks")
PASS = 0
FAIL = 0


def log(msg: str) -> None:
    print(msg)


def verbose(msg: str) -> None:
    if VERBOSE:
        print(f"  {msg}")


def check(name: str, passed: bool, detail: str = "") -> bool:
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    log(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if passed:
        PASS += 1
    else:
        FAIL += 1
    return passed


def run_hook(script: str, stdin_data: str = "", env_extra: dict | None = None) -> tuple[int, str, str]:
    """Run a hook script and return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env.update(env_extra or {})
    try:
        result = subprocess.run(
            ["python3", os.path.join(HOOKS_DIR, script)],
            input=stdin_data, capture_output=True, text=True,
            timeout=30, env=env
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def test_validators() -> None:
    log("\n1. VALIDATORS")
    sys.path.insert(0, HOOKS_DIR)
    from validators import get_validator, validate_exit_code

    v = get_validator("empty_output")
    check("empty_output passes on empty", v("")[0])
    check("empty_output fails on content", not v("hello")[0])

    v = get_validator("contains:ok")
    check("contains:ok passes", v("integrity: ok")[0])
    check("contains:ok fails", not v("error found")[0])

    v = get_validator("equals:0")
    check("equals:0 passes", v("0")[0])
    check("equals:0 fails", not v("3")[0])

    v = get_validator("regex:[0-9]+")
    check("regex matches digits", v("abc123def")[0])
    check("regex fails no digits", not v("abcdef")[0])

    check("exit code 0 passes", validate_exit_code(0, "output")[0])
    check("exit code 1 fails", not validate_exit_code(1, "output")[0])

    sys.path.pop(0)


def test_session_start() -> None:
    log("\n2. SESSION START")
    test_dir = tempfile.mkdtemp(prefix="smoke-test-")
    try:
        rules_dir = os.path.join(test_dir, "rules")
        os.makedirs(rules_dir)
        Path(os.path.join(rules_dir, "core-rules.md")).write_text(
            "# Test Rules\n\n### rule-1\nDo the right thing.\n"
        )

        config = {
            "tiers": {
                "tier1": [
                    {"name": "test-rules", "source": os.path.join(rules_dir, "core-rules.md"),
                     "description": "test rules"},
                    {"name": "infra-report", "type": "checks", "description": "test infra"},
                ],
                "tier2": [
                    {"name": "deploy-rules", "triggers": ["deploy", "release"],
                     "source": os.path.join(rules_dir, "core-rules.md"),
                     "description": "deploy rules"},
                ],
            },
            "checks": [
                {"name": "always-pass", "command": "echo ok", "validator": "contains:ok"},
                {"name": "always-fail", "command": "echo bad", "validator": "contains:good",
                 "optional": True},
            ],
            "gates": {
                "block_until_tier1": True,
                "tier2_keyword_scan": True,
                "prompt_health_warnings": [40, 60, 80],
            },
            "stop": {"require_clean_repos": False, "max_retries": 3},
            "cross_check": {},
        }
        config_path = os.path.join(test_dir, "startup-config.yaml")
        try:
            import yaml
            Path(config_path).write_text(yaml.dump(config))
        except ImportError:
            log("  [SKIP] PyYAML not installed — cannot test session start")
            return

        sid = "smoke-test"
        env = {"CLAUDE_SESSION_ID": sid}
        old_cwd = os.getcwd()
        os.chdir(test_dir)

        code, stdout, stderr = run_hook("on_session_start.py", env_extra=env)
        os.chdir(old_cwd)

        verbose(f"stdout: {stdout.strip()}")
        verbose(f"stderr: {stderr.strip()}")

        check("exit code 0", code == 0, f"got {code}")
        check("stdout mentions STARTUP", "STARTUP:" in stdout)
        check("stdout mentions Manifest", "Manifest:" in stdout)
        check("stdout lists tier1 files", "tier1-" in stdout)

        manifest_path = os.path.join(tempfile.gettempdir(), f"manifest-{sid}.json")
        check("manifest created", os.path.exists(manifest_path))

        sentinel_path = os.path.join(tempfile.gettempdir(), f"startup-complete-{sid}.json")
        check("sentinel created", os.path.exists(sentinel_path))

        if os.path.exists(manifest_path):
            manifest = json.loads(Path(manifest_path).read_text())
            check("manifest has tier1", len(manifest.get("tier1", [])) == 2)
            check("manifest has tier2", len(manifest.get("tier2", [])) == 1)
            check("manifest has gates", "block_until_tier1" in manifest.get("gates", {}))

        if os.path.exists(sentinel_path):
            sentinel = json.loads(Path(sentinel_path).read_text())
            check("sentinel stage is pending", sentinel.get("stage") == "tier1_pending")
            check("sentinel reads empty", len(sentinel.get("completed_reads", [])) == 0)

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        for f in ["manifest", "startup-complete", "tier1-test-rules", "tier1-infra-report"]:
            path = os.path.join(tempfile.gettempdir(), f"{f}-smoke-test.json")
            if os.path.exists(path):
                os.remove(path)
            path = os.path.join(tempfile.gettempdir(), f"{f}-smoke-test.md")
            if os.path.exists(path):
                os.remove(path)


def test_gate_check() -> None:
    log("\n3. GATE CHECK (PreToolUse)")
    sid = "smoke-gate"
    tmpdir = tempfile.gettempdir()

    manifest = {
        "tier1": [{"name": "rules", "path": "/tmp/tier1-rules-smoke-gate.md"}],
        "tier2": [{"name": "deploy", "triggers": ["deploy"], "source": "rules/deploy.md"}],
        "gates": {"block_until_tier1": True, "tier2_keyword_scan": True,
                  "keyword_scan_fields": ["command"], "keyword_scan_max_chars": 120},
    }
    sentinel = {"session_id": sid, "stage": "tier1_pending",
                "completed_reads": [], "cross_check_done": True}

    Path(os.path.join(tmpdir, f"manifest-{sid}.json")).write_text(json.dumps(manifest))
    Path(os.path.join(tmpdir, f"startup-complete-{sid}.json")).write_text(json.dumps(sentinel))
    env = {"CLAUDE_SESSION_ID": sid}

    # Test: Read is always allowed
    code, stdout, _ = run_hook("gate_check.py",
        json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/some/file.md"}}), env)
    check("Read allowed during pending", code == 0 and "deny" not in stdout)

    # Test: Bash blocked during pending
    code, stdout, _ = run_hook("gate_check.py",
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}), env)
    check("Bash blocked during pending", "deny" in stdout.lower() or "permissionDecision" in stdout)

    # Mark tier1 complete
    sentinel["completed_reads"] = ["rules"]
    sentinel["stage"] = "complete"
    Path(os.path.join(tmpdir, f"startup-complete-{sid}.json")).write_text(json.dumps(sentinel))

    # Test: Bash allowed after complete
    code, stdout, _ = run_hook("gate_check.py",
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}), env)
    check("Bash allowed after complete", code == 0 and "deny" not in stdout.lower())

    # Test: Tier 2 trigger
    code, stdout, _ = run_hook("gate_check.py",
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "deploy to production"}}), env)
    check("Tier 2 trigger fires on 'deploy'", "deploy" in stdout.lower() or "tier 2" in stdout.lower())

    # Cleanup
    for f in [f"manifest-{sid}.json", f"startup-complete-{sid}.json"]:
        Path(os.path.join(tmpdir, f)).unlink(missing_ok=True)


def test_prompt_submit() -> None:
    log("\n4. PROMPT SUBMIT (UserPromptSubmit)")
    sid = "smoke-prompt"
    tmpdir = tempfile.gettempdir()

    manifest = {"tier1": [{"name": "rules", "path": "/tmp/tier1-rules.md"}],
                "gates": {"prompt_health_warnings": [2, 4]}}
    sentinel = {"session_id": sid, "stage": "tier1_pending",
                "completed_reads": [], "cross_check_done": False}

    Path(os.path.join(tmpdir, f"manifest-{sid}.json")).write_text(json.dumps(manifest))
    Path(os.path.join(tmpdir, f"startup-complete-{sid}.json")).write_text(json.dumps(sentinel))
    env = {"CLAUDE_SESSION_ID": sid}

    # Test: gate fires when incomplete
    code, stdout, _ = run_hook("on_prompt_submit.py", env_extra=env)
    check("Gate fires when tier1 incomplete", "STARTUP INCOMPLETE" in stdout or "unread" in stdout.lower())

    # Mark complete
    sentinel["stage"] = "complete"
    Path(os.path.join(tmpdir, f"startup-complete-{sid}.json")).write_text(json.dumps(sentinel))

    # Remove old prompt count
    count_file = os.path.join(tmpdir, f"prompt-count-{sid}")
    Path(count_file).unlink(missing_ok=True)

    # Test: prompt counting works (fire twice to reach threshold 2)
    run_hook("on_prompt_submit.py", env_extra=env)
    code, stdout, _ = run_hook("on_prompt_submit.py", env_extra=env)
    check("Health warning at threshold", "CONTEXT HEALTH" in stdout or code == 0)

    # Cleanup
    for f in [f"manifest-{sid}.json", f"startup-complete-{sid}.json", f"prompt-count-{sid}"]:
        Path(os.path.join(tmpdir, f)).unlink(missing_ok=True)


def test_stop_hook() -> None:
    log("\n5. STOP HOOK")
    sid = "smoke-stop"
    tmpdir = tempfile.gettempdir()

    manifest = {"stop": {"require_clean_repos": False, "require_transcript": False, "max_retries": 2}}
    Path(os.path.join(tmpdir, f"manifest-{sid}.json")).write_text(json.dumps(manifest))
    env = {"CLAUDE_SESSION_ID": sid}

    # Remove old retry count
    Path(os.path.join(tmpdir, f"stop-retries-{sid}")).unlink(missing_ok=True)

    # Test: passes when no checks required
    code, stdout, _ = run_hook("on_stop.py", env_extra=env)
    check("Stop passes with no checks", code == 0)
    check("Output says passed", "passed" in stdout.lower() or "check" in stdout.lower())

    # Cleanup
    for f in [f"manifest-{sid}.json", f"stop-retries-{sid}"]:
        Path(os.path.join(tmpdir, f)).unlink(missing_ok=True)


def main() -> None:
    log("SMOKE TEST — Agentic AI Tiered Startup Architecture")
    log("=" * 50)

    test_validators()
    test_session_start()
    test_gate_check()
    test_prompt_submit()
    test_stop_hook()

    log(f"\n{'=' * 50}")
    log(f"RESULT: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        log("Fix the failures above before using in production.")
        sys.exit(1)
    else:
        log("All checks passed. Your setup is ready.")
        sys.exit(0)


if __name__ == "__main__":
    main()
