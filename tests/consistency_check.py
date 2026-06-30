#!/usr/bin/env python3
"""Structural consistency checker for the ai-agent-harness repo.

Verifies that code, docs, config, course, wizard, and nav are all in sync.
Run after any change to catch forgotten cross-references.

Usage:
    python3 tests/consistency_check.py
    python3 tests/consistency_check.py --verbose
"""
from __future__ import annotations
import ast
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
HOOKS_DIR = REPO / "hooks"
DOCS_DIR = REPO / "docs"
CHECKS_DIR = REPO / "checks"


def _skip(path: Path) -> bool:
    """Skip macOS resource forks, pycache, and hidden files."""
    s = str(path)
    return ("__pycache__" in s or "/._" in s or "/.git/" in s
            or path.name.startswith("._"))

PASS = 0
FAIL = 0
WARN = 0
VERBOSE = "--verbose" in sys.argv


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    if VERBOSE:
        print(f"  \033[32m[OK]\033[0m {msg}")


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  \033[31m[FAIL]\033[0m {msg}")


def warn(msg: str) -> None:
    global WARN
    WARN += 1
    print(f"  \033[33m[WARN]\033[0m {msg}")


def section(title: str) -> None:
    print(f"\n{title}")


# ── 1. Every hook .py file has valid syntax ──────────────────────────
def check_syntax():
    section("1. PYTHON SYNTAX")
    for py in sorted(HOOKS_DIR.glob("*.py")):
        if _skip(py):
            continue
        try:
            ast.parse(py.read_text())
            ok(f"{py.name}")
        except SyntaxError as e:
            fail(f"{py.name}: {e}")
    for py in [REPO / "setup.py", REPO / "tests" / "smoke_test.py"]:
        if py.exists():
            try:
                ast.parse(py.read_text())
                ok(f"{py.name}")
            except SyntaxError as e:
                fail(f"{py.name}: {e}")


# ── 2. Every hook is referenced in setup.py ──────────────────────────
def check_hooks_in_wizard():
    section("2. HOOKS IN SETUP WIZARD")
    setup = (REPO / "setup.py").read_text()
    for py in sorted(HOOKS_DIR.glob("*.py")):
        if _skip(py) or py.name in ("validators.py", "__init__.py"):
            continue
        if py.name in setup:
            ok(f"{py.name} referenced in setup.py")
        else:
            warn(f"{py.name} NOT referenced in setup.py")


# ── 3. Every doc page is in mkdocs.yml nav ───────────────────────────
def check_nav_coverage():
    section("3. DOCS IN MKDOCS NAV")
    mkdocs = (REPO / "mkdocs.yml").read_text()
    for md in sorted(DOCS_DIR.rglob("*.md")):
        if _skip(md):
            continue
        rel = md.relative_to(DOCS_DIR)
        rel_str = str(rel)
        if rel.name in ("index.md", "README.md"):
            continue
        if rel_str in mkdocs or rel.name.replace(".md", "") in mkdocs:
            ok(f"{rel_str} in nav")
        else:
            warn(f"{rel_str} NOT in mkdocs.yml nav")


# ── 4. Config keys in code match config.example.yaml ─────────────────
def check_config_keys():
    section("4. CONFIG KEYS")
    example = (REPO / "config.example.yaml").read_text()

    keys_in_code = set()
    for py in [p for p in HOOKS_DIR.glob("*.py") if not _skip(p)]:
        content = py.read_text()
        for m in re.findall(r'\.get\(["\']([a-z_]+)["\']\)', content):
            if m not in ("command", "name", "validator", "fail_message",
                         "source", "type", "triggers", "path", "description",
                         "critical", "optional", "phase", "auto_heal",
                         "heal_command", "expected", "stage",
                         "completed_reads", "cross_check_done",
                         "fact_check_done", "write_back_suggestions",
                         "audit_checks_path", "file_path", "tool_name"):
                keys_in_code.add(m)

    for key in sorted(keys_in_code):
        if key in example:
            ok(f"'{key}' in config.example.yaml")
        else:
            warn(f"'{key}' used in hooks but NOT in config.example.yaml")


# ── 5. Markdown links point to existing files ────────────────────────
def check_links():
    section("5. MARKDOWN LINKS")
    broken = []
    for md in sorted(f for f in DOCS_DIR.rglob("*.md") if not _skip(f)):
        content = md.read_text()
        parent = md.parent
        for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', content):
            target = m.group(2)
            if target.startswith("http") or target.startswith("#") or target.startswith("mailto:"):
                continue
            target_clean = target.split("#")[0].split("?")[0]
            if not target_clean:
                continue
            resolved = (parent / target_clean).resolve()
            if not resolved.exists():
                broken.append((md.relative_to(REPO), target_clean))

    if not broken:
        ok("All local markdown links resolve")
    else:
        for src, target in broken[:10]:
            fail(f"{src} -> {target} (not found)")


# ── 6. Features in code are documented ───────────────────────────────
def check_feature_docs():
    section("6. FEATURE DOCUMENTATION")
    all_docs = ""
    for md in (f for f in DOCS_DIR.rglob("*.md") if not _skip(f)):
        all_docs += md.read_text().lower()
    readme = (REPO / "README.md").read_text().lower()
    all_text = all_docs + readme

    features = {
        "rule_zero": ["rule zero", "rule-zero", "scattered"],
        "self_verification": ["self-verification", "self_verification", "re-run verification"],
        "self_healing": ["self-healing", "self_healing", "write_back_suggestions"],
        "audit_runner": ["audit runner", "audit.py", "audit-checks.yaml"],
        "git_passthrough": ["git commit.*passthrough", "git.*auto-allow", "version control.*never blocked"],
        "shutdown_steps": ["shutdown_steps", "shutdown steps"],
        "session_summary": ["require_session_summary", "session summary"],
        "edit_logging": ["edit logging", "rule_log"],
        "stale_facts": ["stale fact", "system_facts", "fact_references"],
        "cross_check": ["cross-check", "cross_check", "drift detection"],
        "tier2_triggers": ["tier.2", "keyword trigger", "tier2_keyword_scan"],
    }

    for feature, patterns in features.items():
        found = any(re.search(p, all_text) for p in patterns)
        if found:
            ok(f"'{feature}' documented")
        else:
            fail(f"'{feature}' NOT found in any docs")


# ── 7. Course modules cover all levels ───────────────────────────────
def check_course_coverage():
    section("7. COURSE COVERAGE")
    course_dir = DOCS_DIR / "course"
    if not course_dir.exists():
        warn("No course/ directory")
        return

    all_course = ""
    for md in sorted(f for f in course_dir.glob("module-*.md") if not _skip(f)):
        all_course += md.read_text().lower()

    level_features = {
        "level_1": ["sessionstart", "manifest", "tier1"],
        "level_2": ["pretooluse", "gate", "block_until_tier1"],
        "level_3": ["tier.2", "keyword", "cross.check"],
        "level_4": ["posttooluse", "on_edit", "on_stop", "stop hook", "audit"],
    }

    for level, patterns in level_features.items():
        found = sum(1 for p in patterns if re.search(p, all_course))
        if found >= 2:
            ok(f"{level}: {found}/{len(patterns)} key terms in course")
        else:
            fail(f"{level}: only {found}/{len(patterns)} key terms in course")


# ── 8. YAML files parse correctly ────────────────────────────────────
def check_yaml():
    section("8. YAML VALIDITY")
    try:
        import yaml
    except ImportError:
        warn("PyYAML not installed — skipping YAML checks")
        return

    for yf in sorted(CHECKS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(yf.read_text())
            checks = data.get("checks", [])
            ok(f"{yf.name}: {len(checks)} checks")
        except Exception as e:
            fail(f"{yf.name}: {e}")

    config = REPO / "config.example.yaml"
    if config.exists():
        try:
            yaml.safe_load(config.read_text())
            ok("config.example.yaml parses")
        except Exception as e:
            fail(f"config.example.yaml: {e}")


# ── 9. No sensitive data ─────────────────────────────────────────────
def check_sensitive():
    section("9. SENSITIVE DATA SCAN")
    # Load patterns from config file if available, otherwise use examples.
    # Users should customize sensitive-patterns.txt with their own personal
    # data, internal domains, and project-specific strings to scan for.
    patterns_file = REPO / "tests" / "sensitive-patterns.txt"
    if patterns_file.exists():
        patterns = [
            line.strip() for line in patterns_file.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        # Generic examples — replace with your own patterns
        patterns = [
            r'your-username', r'your-internal-domain\.com',
        ]
    regex = re.compile("|".join(patterns), re.IGNORECASE)
    found = []
    for ext in ("*.py", "*.md", "*.yaml", "*.yml", "*.json"):
        for f in REPO.rglob(ext):
            if "__pycache__" in str(f) or "node_modules" in str(f):
                continue
            if ".git" in f.parts or f.name == "consistency_check.py":
                continue
            try:
                content = f.read_text()
                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        found.append((f.relative_to(REPO), i, line.strip()[:80]))
            except Exception:
                pass

    if not found:
        ok("No sensitive data found")
    else:
        for fpath, line_no, snippet in found[:10]:
            fail(f"{fpath}:{line_no}: {snippet}")


# ── 10. Smoke test count matches ─────────────────────────────────────
def check_test_coverage():
    section("10. TEST COVERAGE")
    smoke = (REPO / "tests" / "smoke_test.py").read_text()
    test_fns = re.findall(r'^def (test_\w+)', smoke, re.MULTILINE)
    main_calls = re.findall(r'(test_\w+)\(\)', smoke)

    for fn in test_fns:
        if fn in main_calls:
            ok(f"{fn}() called in main()")
        else:
            fail(f"{fn}() defined but NOT called in main()")


def main():
    print("STRUCTURAL CONSISTENCY CHECK")
    print("=" * 50)

    check_syntax()
    check_hooks_in_wizard()
    check_nav_coverage()
    check_config_keys()
    check_links()
    check_feature_docs()
    check_course_coverage()
    check_yaml()
    check_sensitive()
    check_test_coverage()

    print(f"\n{'=' * 50}")
    print(f"RESULT: {PASS} passed, {FAIL} failed, {WARN} warnings")
    if FAIL > 0:
        print("Fix the failures above.")
        sys.exit(1)
    elif WARN > 0:
        print("Warnings are advisory — review but may be intentional.")
        sys.exit(0)
    else:
        print("All checks passed. Repo is structurally consistent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
