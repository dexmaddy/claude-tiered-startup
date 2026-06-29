#!/usr/bin/env python3
"""Standalone audit runner: on-demand infrastructure and quality checks.

Reads checks from a YAML file, runs each command, validates output
using the validator framework, and reports pass/fail.

Usage:
    python3 hooks/audit.py
    python3 hooks/audit.py --checks path/to/audit-checks.yaml
    python3 hooks/audit.py --verbose
    python3 hooks/audit.py --critical-only

Importable by other hooks:
    from audit import run_audit
    summary = run_audit("checks/audit-checks.yaml")
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validators import get_validator, validate_exit_code

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def find_checks_file(cli_path: str | None = None) -> Path:
    """Locate audit-checks.yaml. Search: cli_path, cwd/checks/, up from cwd, repo default."""
    if cli_path:
        p = Path(cli_path)
        if p.exists():
            return p
        print(f"Error: {cli_path} not found", file=sys.stderr)
        sys.exit(1)

    candidates = [
        Path.cwd() / "checks" / "audit-checks.yaml",
        Path.cwd() / "audit-checks.yaml",
        Path(__file__).parent.parent / "checks" / "audit-checks.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c

    print("Error: No audit-checks.yaml found. Use --checks to specify.", file=sys.stderr)
    sys.exit(1)


def load_checks(checks_path: Path) -> list[dict]:
    """Load checks from YAML file."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(checks_path.read_text())
    checks = data.get("checks", [])
    if not checks:
        print(f"Warning: No checks found in {checks_path}", file=sys.stderr)
    return checks


def run_single_check(check: dict) -> dict:
    """Run one check and return result dict."""
    name = check.get("name", "unnamed")
    command = check.get("command", "")
    validator_spec = check.get("validator", "")
    is_optional = check.get("optional", False)
    is_critical = check.get("critical", True)

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        stdout = result.stdout

        if validator_spec:
            validator = get_validator(validator_spec)
            passed, detail = validator(stdout)
        else:
            passed, detail = validate_exit_code(result.returncode, stdout)

    except subprocess.TimeoutExpired:
        passed, detail = False, "timeout (30s)"
    except Exception as e:
        passed, detail = False, str(e)[:200]

    if passed:
        status = "OK"
    elif is_optional:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "name": name,
        "status": status,
        "detail": detail,
        "critical": is_critical,
        "phase": check.get("phase", ""),
    }


def run_audit(
    checks_path: str | Path | None = None,
    critical_only: bool = False,
) -> dict:
    """Run all checks and return summary. Main entry point for imports."""
    path = find_checks_file(str(checks_path) if checks_path else None)
    checks = load_checks(path)

    if critical_only:
        checks = [c for c in checks if c.get("critical", True)]

    results = [run_single_check(c) for c in checks]

    passed = sum(1 for r in results if r["status"] == "OK")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    warned = sum(1 for r in results if r["status"] == "WARN")
    critical_failed = sum(1 for r in results if r["status"] == "FAIL" and r["critical"])

    return {
        "results": results,
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "critical_failed": critical_failed,
        "all_critical_pass": critical_failed == 0,
    }


def format_report(summary: dict, verbose: bool = False) -> str:
    """Format results for terminal output with ANSI colors."""
    lines = []
    for r in summary["results"]:
        color = {"OK": GREEN, "FAIL": RED, "WARN": YELLOW}.get(r["status"], "")
        crit = " [critical]" if r["critical"] and r["status"] == "FAIL" else ""
        lines.append(f"  {color}[{r['status']}]{RESET} {r['name']}{crit}")
        if verbose and r["detail"]:
            lines.append(f"         {r['detail'][:120]}")

    lines.append("")
    lines.append(
        f"{BOLD}Result:{RESET} "
        f"{GREEN}{summary['passed']} passed{RESET}, "
        f"{RED}{summary['failed']} failed{RESET}, "
        f"{YELLOW}{summary['warned']} warned{RESET}"
    )
    if summary["critical_failed"]:
        lines.append(f"{RED}{BOLD}{summary['critical_failed']} critical failure(s){RESET}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run audit checks")
    parser.add_argument("--checks", help="Path to audit-checks.yaml")
    parser.add_argument("--verbose", action="store_true", help="Show check details")
    parser.add_argument("--critical-only", action="store_true", help="Only run critical checks")
    args = parser.parse_args()

    summary = run_audit(checks_path=args.checks, critical_only=args.critical_only)
    print(format_report(summary, verbose=args.verbose))
    sys.exit(0 if summary["all_critical_pass"] else 1)


if __name__ == "__main__":
    main()
