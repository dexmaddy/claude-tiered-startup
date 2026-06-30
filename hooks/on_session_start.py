#!/usr/bin/env python3
"""SessionStart hook: read config, run checks, generate tier files, write manifest.

Level 1 of the AI Agent Harness.
Reads startup-config.yaml, runs infrastructure checks with output-based validators,
copies/generates tier1 files to temp, and writes a manifest for Claude to follow.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from validators import get_validator, validate_exit_code

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "default")
TMPDIR = tempfile.gettempdir()


def find_config() -> Path:
    """Walk up from CWD looking for startup-config.yaml."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / "startup-config.yaml"
        if candidate.exists():
            return candidate
    print("ERROR: startup-config.yaml not found in any parent directory", file=sys.stderr)
    sys.exit(1)


def run_checks(checks: list[dict]) -> list[dict]:
    results = []
    for check in checks:
        name = check["name"]
        try:
            proc = subprocess.run(
                check["command"], shell=True, capture_output=True, text=True, timeout=30
            )
            stdout = proc.stdout
            validator_spec = check.get("validator")
            if validator_spec:
                passed, detail = get_validator(validator_spec)(stdout)
            else:
                passed, detail = validate_exit_code(proc.returncode, stdout)
        except subprocess.TimeoutExpired:
            passed, detail = False, "timeout after 30s"
        except Exception as e:
            passed, detail = False, str(e)

        status = "OK" if passed else ("WARN" if check.get("optional") else "FAIL")
        results.append({"name": name, "status": status, "detail": detail})
    return results


def generate_infra_report(check_results: list[dict]) -> str:
    lines = ["# Infrastructure Report (auto-generated)", f"Time: {__import__('datetime').datetime.now():%Y-%m-%d %H:%M}", ""]
    ok = sum(1 for r in check_results if r["status"] == "OK")
    fail = sum(1 for r in check_results if r["status"] == "FAIL")
    warn = sum(1 for r in check_results if r["status"] == "WARN")
    for r in check_results:
        lines.append(f"- [{r['status']}] {r['name']}: {r['detail']}")
    lines.append(f"\n**Result: {ok} OK, {fail} FAIL, {warn} WARN**")
    return "\n".join(lines)


def prepare_tier_files(tier_defs: list[dict], prefix: str, check_results: list[dict] | None = None) -> list[dict]:
    manifest_entries = []
    for item in tier_defs:
        name = item["name"]
        out_path = os.path.join(TMPDIR, f"{prefix}{name}-{SESSION_ID}.md")

        if item.get("type") == "checks" and check_results:
            content = generate_infra_report(check_results)
            Path(out_path).write_text(content)
        elif item.get("type") == "generated":
            try:
                proc = subprocess.run(item["source"], shell=True, capture_output=True, text=True, timeout=60)
                Path(out_path).write_text(proc.stdout)
            except Exception as e:
                Path(out_path).write_text(f"# Generation failed: {e}")
        else:
            src = Path(item["source"])
            if src.exists():
                shutil.copy2(src, out_path)
            else:
                Path(out_path).write_text(f"# Source not found: {item['source']}")

        line_count = len(Path(out_path).read_text().splitlines())
        manifest_entries.append({
            "name": name,
            "path": out_path,
            "lines": line_count,
            "description": item.get("description", ""),
            "source": item.get("source", "checks"),
        })
    return manifest_entries


def write_manifest(tier1_entries: list[dict], tier2_defs: list[dict], config: dict) -> str:
    manifest_path = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
    manifest = {
        "session_id": SESSION_ID,
        "tier1": tier1_entries,
        "tier2": [
            {"name": t["name"], "triggers": t.get("triggers", []),
             "source": t["source"], "description": t.get("description", "")}
            for t in tier2_defs
        ],
        "gates": config.get("gates", {}),
        "stop": config.get("stop", {}),
        "cross_check": config.get("cross_check", {}),
    }
    Path(manifest_path).write_text(json.dumps(manifest, indent=2))
    return manifest_path


def write_sentinel(stage: str = "tier1_pending") -> str:
    sentinel_path = os.path.join(TMPDIR, f"startup-complete-{SESSION_ID}.json")
    Path(sentinel_path).write_text(json.dumps({
        "session_id": SESSION_ID,
        "stage": stage,
        "completed_reads": [],
        "cross_check_done": False,
    }, indent=2))
    return sentinel_path


def main() -> None:
    config_path = find_config()
    config = yaml.safe_load(config_path.read_text())

    checks = config.get("checks", [])
    check_results = run_checks(checks) if checks else []

    tier1_defs = config.get("tiers", {}).get("tier1", [])
    tier2_defs = config.get("tiers", {}).get("tier2", [])

    tier1_entries = prepare_tier_files(tier1_defs, "tier1-", check_results)
    manifest_path = write_manifest(tier1_entries, tier2_defs, config)
    write_sentinel()

    ok = sum(1 for r in check_results if r["status"] == "OK")
    fail = sum(1 for r in check_results if r["status"] == "FAIL")
    total_lines = sum(e["lines"] for e in tier1_entries)

    print(f"STARTUP: {ok} OK, {fail} FAIL")
    print(f"Manifest: {manifest_path}")
    print(f"Tier 1: {len(tier1_entries)} files ({total_lines} lines)")
    print(f"Tier 2: {len(tier2_defs)} files (on-demand)")
    print("ACTION REQUIRED: Read manifest, then read all Tier 1 files.")
    for e in tier1_entries:
        print(f"  - {e['path']} ({e['lines']} lines, {e['name']})")


if __name__ == "__main__":
    main()
