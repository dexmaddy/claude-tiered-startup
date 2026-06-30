#!/usr/bin/env python3
"""Cross-check drift detection: compare expected state vs actual.

Level 3 of the AI Agent Harness.
Runs once per session after Tier 1 loads. Compares expected counts/values
from the manifest against live checks, auto-heals safe items, logs the rest.

Bounded: 2 passes max (detect → fix → re-check → log remaining). No loops.
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


def read_json(path: str) -> dict | None:
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run_count_check(command: str) -> int | None:
    """Run a command that should return a single integer."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return None


def run_cross_check(expected: dict[str, dict]) -> dict:
    """Compare expected values against live checks.

    expected format:
      {"rule_count": {"command": "wc -l < rules.md", "expected": 58, "auto_heal": false},
       "file_count": {"command": "ls docs/*.md | wc -l", "expected": 12, "auto_heal": true}}
    """
    results = {"passed": [], "drifted": [], "healed": [], "errors": []}

    for name, check in expected.items():
        command = check.get("command", "")
        expected_val = check.get("expected")
        auto_heal = check.get("auto_heal", False)

        actual = run_count_check(command)
        if actual is None:
            results["errors"].append({"name": name, "reason": "command failed or non-integer output"})
            continue

        if actual == expected_val:
            results["passed"].append({"name": name, "value": actual})
        else:
            entry = {"name": name, "expected": expected_val, "actual": actual}
            if auto_heal and check.get("heal_command"):
                try:
                    subprocess.run(check["heal_command"], shell=True, timeout=10)
                    results["healed"].append(entry)
                except Exception:
                    results["drifted"].append(entry)
            else:
                results["drifted"].append(entry)

    return results


def main() -> None:
    manifest = read_json(MANIFEST)
    sentinel = read_json(SENTINEL)

    if not manifest or not sentinel:
        print("No manifest or sentinel — skipping cross-check")
        sys.exit(0)

    if sentinel.get("cross_check_done"):
        print("Cross-check already completed this session")
        sys.exit(0)

    expected = manifest.get("cross_check", {}).get("expected_counts", {})
    if not expected:
        print("No cross-check expectations in manifest — skipping")
        sentinel["cross_check_done"] = True
        Path(SENTINEL).write_text(json.dumps(sentinel, indent=2))
        sys.exit(0)

    # Pass 1: detect and auto-heal
    results = run_cross_check(expected)

    # Pass 2: re-check healed items only
    if results["healed"]:
        recheck = {item["name"]: expected[item["name"]] for item in results["healed"]}
        pass2 = run_cross_check(recheck)
        for item in pass2["drifted"]:
            results["drifted"].append(item)
        results["healed"] = [h for h in results["healed"]
                             if h["name"] not in {d["name"] for d in pass2["drifted"]}]

    # Mark done (no more passes — bounded)
    sentinel["cross_check_done"] = True
    sentinel["cross_check_results"] = {
        "passed": len(results["passed"]),
        "drifted": len(results["drifted"]),
        "healed": len(results["healed"]),
        "errors": len(results["errors"]),
    }
    Path(SENTINEL).write_text(json.dumps(sentinel, indent=2))

    # Write-back suggestions: for persistent drift, suggest concrete fixes
    suggestions = []
    for d in results["drifted"]:
        name = d["name"]
        check = expected.get(name, {})
        if check.get("heal_command"):
            suggestions.append(
                f"SUGGESTED FIX for '{name}': update expected value in manifest "
                f"({d['expected']} -> {d['actual']}), or fix the source."
            )
        else:
            suggestions.append(
                f"UNRESOLVED DRIFT '{name}': expected {d['expected']}, got {d['actual']}. "
                "Update manifest or investigate."
            )
    if suggestions:
        sentinel["write_back_suggestions"] = suggestions
        Path(SENTINEL).write_text(json.dumps(sentinel, indent=2))

    # Report
    total = sum(len(v) for v in results.values())
    print(f"Cross-check: {len(results['passed'])}/{total} passed", end="")
    if results["healed"]:
        print(f", {len(results['healed'])} auto-healed", end="")
    if results["drifted"]:
        print(f", {len(results['drifted'])} DRIFTED", end="")
        for d in results["drifted"]:
            print(f"\n  DRIFT: {d['name']}: expected {d['expected']}, got {d['actual']}", end="")
    if results["errors"]:
        print(f", {len(results['errors'])} errors", end="")
    print()
    for s in suggestions:
        print(s)


if __name__ == "__main__":
    main()
