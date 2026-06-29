#!/usr/bin/env python3
"""Interactive setup wizard for the Agentic AI Tiered Startup Architecture.

Guides first-time users through:
  1. Choosing their AI agent platform (Claude Code, Cursor, Windsurf, Aider, custom)
  2. Choosing their data store (JSON/YAML files, SQLite, PostgreSQL)
  3. Choosing their startup level (1-4)
  4. Generating the config, hook scripts, and settings files
  5. Creating sample rules and running a verification check

Usage:
    python3 setup.py                # Interactive wizard
    python3 setup.py --non-interactive --platform claude --store yaml --level 2
"""
from __future__ import annotations
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent
HOOKS_DIR = REPO_DIR / "hooks"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, options: list[str], default: int = 1) -> int:
    """Display a numbered menu and return the 1-based choice."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if i == default else ""
        print(f"  {i}. {opt}{marker}")
    while True:
        raw = input(f"\nYour choice [1-{len(options)}]: ").strip()
        if raw == "":
            return default
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def ask_text(prompt: str, default: str = "") -> str:
    """Ask for free-text input with an optional default."""
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def confirm(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    suffix = " [Y/n]" if default else " [y/N]"
    raw = input(f"{prompt}{suffix}: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


def copy_hook(src_name: str, dest_dir: Path) -> None:
    """Copy a hook script from the repo to the destination."""
    src = HOOKS_DIR / src_name
    dest = dest_dir / src_name
    if src.exists():
        shutil.copy2(src, dest)


def banner() -> None:
    print("=" * 60)
    print("  Agentic AI Tiered Startup — Setup Wizard")
    print("=" * 60)
    print()
    print("This wizard will configure the tiered startup architecture")
    print("for your AI coding agent and project.")
    print()


# ---------------------------------------------------------------------------
# Step 1: Platform
# ---------------------------------------------------------------------------

PLATFORMS = {
    1: {
        "name": "Claude Code",
        "hooks_dir": ".claude/hooks",
        "settings_file": ".claude/settings.json",
        "instructions_file": "CLAUDE.md",
        "has_hooks": True,
        "notes": "Full hook support (SessionStart, PreToolUse, UserPromptSubmit, PostToolUse, Stop)",
    },
    2: {
        "name": "Cursor",
        "hooks_dir": ".cursor/hooks",
        "settings_file": ".cursor/settings.json",
        "instructions_file": ".cursorrules",
        "has_hooks": False,
        "notes": "Use .cursorrules for rules. Hooks require custom middleware.",
    },
    3: {
        "name": "Windsurf",
        "hooks_dir": ".windsurf/hooks",
        "settings_file": ".windsurf/settings.json",
        "instructions_file": ".windsurfrules",
        "has_hooks": False,
        "notes": "Use .windsurfrules and Cascade memories. Hooks require custom setup.",
    },
    4: {
        "name": "Aider",
        "hooks_dir": ".aider/hooks",
        "settings_file": ".aider.conf.yml",
        "instructions_file": ".aider.conf.yml",
        "has_hooks": False,
        "notes": "Use --read flag for tier1 loading. Limited hook support.",
    },
    5: {
        "name": "Custom / Other",
        "hooks_dir": ".agent/hooks",
        "settings_file": ".agent/settings.json",
        "instructions_file": "AGENT.md",
        "has_hooks": True,
        "notes": "Generic setup. Adapt hook wiring to your agent's lifecycle events.",
    },
}


def step_platform() -> dict:
    choice = ask(
        "Which AI coding agent do you use?",
        [f"{p['name']} — {p['notes']}" for p in PLATFORMS.values()],
        default=1,
    )
    platform = PLATFORMS[choice]
    print(f"\n  Selected: {platform['name']}")
    if not platform["has_hooks"]:
        print(f"\n  Note: {platform['name']} has limited hook support.")
        print("  The startup script will still generate manifests and tier files,")
        print("  but gate enforcement may need custom middleware in your agent.")
    return platform


# ---------------------------------------------------------------------------
# Step 2: Data Store
# ---------------------------------------------------------------------------

STORES = {
    1: {
        "name": "YAML + Markdown files",
        "script": "on_session_start.py",
        "deps": ["pyyaml"],
        "description": "Simple, human-readable, version-controlled. Best for under ~50 rules.",
    },
    2: {
        "name": "SQLite database",
        "script": "on_session_start_db.py",
        "deps": [],
        "description": "Queryable, handles concurrency, tracks history. Python stdlib, no server needed.",
    },
    3: {
        "name": "PostgreSQL database",
        "script": "on_session_start_db.py",
        "deps": ["psycopg2-binary"],
        "description": "Full relational DB. Best for teams, CI/CD pipelines, or existing Postgres infrastructure.",
    },
}


def step_store() -> dict:
    choice = ask(
        "Where should rules and configuration be stored?",
        [f"{s['name']} — {s['description']}" for s in STORES.values()],
        default=1,
    )
    store = STORES[choice]
    print(f"\n  Selected: {store['name']}")

    if choice == 3:
        print("\n  PostgreSQL support uses the same DB schema as SQLite.")
        print("  You'll need to provide a connection string (e.g., postgresql://user:pass@host/db).")
        store["pg_conn"] = ask_text("  PostgreSQL connection string", "postgresql://localhost/agent_rules")

    return store


# ---------------------------------------------------------------------------
# Step 3: Level
# ---------------------------------------------------------------------------

LEVELS = {
    1: "Level 1 — Manifest only (no gates, voluntary compliance)",
    2: "Level 2 — Add gates (enforce rule loading before work)",
    3: "Level 3 — Add tier2 triggers + drift detection",
    4: "Level 4 — Full architecture (all hooks + stop hook + post-write actions)",
}


def step_level() -> int:
    choice = ask(
        "What level of enforcement do you want to start with?",
        list(LEVELS.values()),
        default=2,
    )
    print(f"\n  Selected: {LEVELS[choice]}")
    return choice


# ---------------------------------------------------------------------------
# Step 4: Project Details
# ---------------------------------------------------------------------------

def step_project() -> dict:
    print("\n--- Project Details ---")
    project_name = ask_text("Project name", os.path.basename(os.getcwd()))
    project_dir = ask_text("Project directory", os.getcwd())

    include_ah_rules = confirm("Include anti-hallucination rules in Tier 1?")
    include_backlog = confirm("Enable persistent backlog (session continuity)?")

    return {
        "name": project_name,
        "dir": project_dir,
        "include_ah_rules": include_ah_rules,
        "include_backlog": include_backlog,
    }


# ---------------------------------------------------------------------------
# Step 5: Generate
# ---------------------------------------------------------------------------

def generate(platform: dict, store: dict, level: int, project: dict) -> None:
    project_dir = Path(project["dir"])
    hooks_dir = project_dir / platform["hooks_dir"]
    rules_dir = project_dir / "rules"

    print(f"\n{'=' * 60}")
    print("  Generating configuration...")
    print(f"{'=' * 60}")

    # Create directories
    hooks_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)

    # Copy hook scripts based on level
    copy_hook("validators.py", hooks_dir)
    copy_hook(store["script"], hooks_dir)
    if store["script"] != "on_session_start.py":
        # Rename DB variant to standard name for settings.json
        (hooks_dir / store["script"]).rename(hooks_dir / "on_session_start.py")

    if level >= 2:
        copy_hook("gate_check.py", hooks_dir)
        copy_hook("on_prompt_submit.py", hooks_dir)

    if level >= 3:
        copy_hook("cross_check.py", hooks_dir)

    if level >= 4:
        copy_hook("on_edit.py", hooks_dir)
        copy_hook("on_stop.py", hooks_dir)

    # Copy anti-hallucination rules
    if project["include_ah_rules"]:
        src = REPO_DIR / "rules" / "anti-hallucination-rules.md"
        if src.exists():
            # Strip Jekyll front matter for non-website use
            content = src.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip() + "\n"
            (rules_dir / "anti-hallucination-rules.md").write_text(content)
            print(f"  [OK] Anti-hallucination rules -> {rules_dir}/anti-hallucination-rules.md")

    # Create sample core rules
    sample_rules = rules_dir / "core-rules.md"
    if not sample_rules.exists():
        sample_rules.write_text(
            f"# Core Rules for {project['name']}\n\n"
            "These rules prevent the most common mistakes in this project.\n"
            "Every rule exists because the mistake actually happened.\n\n"
            "### example-rule\n\n"
            "Replace this with your first real rule.\n\n"
            "- DO: [correct behavior]\n"
            "- DON'T: [the mistake]\n\n"
            "**Why:** [What went wrong]\n"
            "**How to apply:** [When to check this rule]\n"
        )
        print(f"  [OK] Sample rules -> {sample_rules}")

    # Generate config (YAML method)
    if store["name"].startswith("YAML"):
        config = _generate_yaml_config(level, project)
        config_path = project_dir / "startup-config.yaml"
        try:
            import yaml
            config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
        except ImportError:
            config_path.write_text(json.dumps(config, indent=2))
        print(f"  [OK] Config -> {config_path}")

    # Initialize DB (SQLite method)
    elif store["name"].startswith("SQLite"):
        db_path = project_dir / "project.db"
        subprocess.run(
            [sys.executable, str(hooks_dir / "on_session_start.py"), "--init-db", str(db_path)],
            cwd=str(project_dir),
        )
        print(f"  [OK] Database -> {db_path}")

    # PostgreSQL note
    elif store["name"].startswith("PostgreSQL"):
        print(f"\n  PostgreSQL setup:")
        print(f"  1. Create the database using the schema from on_session_start_db.py --init-db")
        print(f"  2. Set AGENT_DB_PATH={store.get('pg_conn', 'your-connection-string')}")
        print(f"  3. The hook script will need psycopg2 adapter (modify sqlite3 calls)")

    # Generate settings.json
    settings = _generate_settings(platform, level)
    settings_path = project_dir / platform["settings_file"]
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  [OK] Settings -> {settings_path}")

    # Create backlog file if requested
    if project["include_backlog"] and store["name"].startswith("YAML"):
        backlog_path = project_dir / "backlog.json"
        if not backlog_path.exists():
            backlog_path.write_text(json.dumps({
                "tasks": [],
                "last_session": None,
            }, indent=2) + "\n")
            print(f"  [OK] Backlog -> {backlog_path}")

    # Update agent instructions file
    instructions_path = project_dir / platform["instructions_file"]
    if not instructions_path.exists() or confirm(f"\nAppend startup instructions to {platform['instructions_file']}?"):
        _append_instructions(instructions_path, platform)
        print(f"  [OK] Instructions -> {instructions_path}")

    # Install dependencies
    if store["deps"]:
        print(f"\n  Installing dependencies: {', '.join(store['deps'])}")
        subprocess.run([sys.executable, "-m", "pip", "install", *store["deps"], "-q"])

    # Summary
    print(f"\n{'=' * 60}")
    print("  Setup Complete!")
    print(f"{'=' * 60}")
    print(f"\n  Platform:     {platform['name']}")
    print(f"  Data store:   {store['name']}")
    print(f"  Level:        {level}")
    print(f"  Hooks dir:    {hooks_dir}")
    print(f"  Rules dir:    {rules_dir}")
    print(f"  Settings:     {settings_path}")
    print(f"\n  Next steps:")
    print(f"  1. Edit {rules_dir}/core-rules.md with your project's actual rules")
    print(f"  2. Start a new {platform['name']} session to test")
    print(f"  3. Verify the startup output shows your tier1 files")
    if level >= 2:
        print(f"  4. Try using a tool before reading tier1 — it should be blocked")
    print(f"\n  Run the smoke test:")
    print(f"  python3 {REPO_DIR}/tests/smoke_test.py --verbose")


def _generate_yaml_config(level: int, project: dict) -> dict:
    tier1 = [
        {"name": "core-rules", "source": "rules/core-rules.md",
         "description": "Project rules and conventions"},
        {"name": "infra-report", "type": "checks",
         "description": "Infrastructure health"},
    ]
    if project["include_ah_rules"]:
        tier1.insert(1, {
            "name": "ah-rules", "source": "rules/anti-hallucination-rules.md",
            "description": "Anti-hallucination rules for faithful outputs",
        })

    config: dict = {
        "tiers": {"tier1": tier1, "tier2": []},
        "checks": [
            {"name": "git-clean", "command": "git status --porcelain",
             "validator": "empty_output", "fail_message": "Uncommitted changes"},
        ],
        "gates": {
            "block_until_tier1": level >= 2,
            "tier2_keyword_scan": level >= 3,
            "prompt_health_warnings": [40, 60, 80],
        },
    }

    if level >= 4:
        config["stop"] = {"require_clean_repos": True, "max_retries": 8}

    if project["include_backlog"]:
        config["tiers"]["tier1"].append({
            "name": "backlog", "source": "scripts/gen_backlog.sh",
            "type": "generated", "description": "Active tasks and session continuity",
        })

    return config


def _generate_settings(platform: dict, level: int) -> dict:
    hooks_path = platform["hooks_dir"]
    settings: dict = {"hooks": {}}

    settings["hooks"]["SessionStart"] = [{
        "matcher": "",
        "hooks": [{"type": "command",
                    "command": f"python3 {hooks_path}/on_session_start.py",
                    "timeout": 60000}],
    }]

    if level >= 2:
        settings["hooks"]["PreToolUse"] = [{
            "matcher": "",
            "hooks": [{"type": "command",
                        "command": f"python3 {hooks_path}/gate_check.py",
                        "timeout": 5000}],
        }]
        settings["hooks"]["UserPromptSubmit"] = [{
            "matcher": "",
            "hooks": [{"type": "command",
                        "command": f"python3 {hooks_path}/on_prompt_submit.py",
                        "timeout": 5000}],
        }]

    if level >= 4:
        settings["hooks"]["PostToolUse"] = [{
            "matcher": "Write|Edit",
            "hooks": [{"type": "command",
                        "command": f"python3 {hooks_path}/on_edit.py",
                        "timeout": 5000}],
        }]
        settings["hooks"]["Stop"] = [{
            "matcher": "",
            "hooks": [{"type": "command",
                        "command": f"python3 {hooks_path}/on_stop.py",
                        "timeout": 10000}],
        }]

    return settings


def _append_instructions(path: Path, platform: dict) -> None:
    startup_text = """
## Startup

This project uses the Tiered Startup Architecture.
At session start, the SessionStart hook generates a manifest and tier1 files.
Read the manifest from hook output, then read ALL tier1 files before doing
any work. Gates enforce this — tools are blocked until all files are read.

Do NOT skip startup. Do NOT explain what startup does — just do it.
"""
    if path.exists():
        content = path.read_text()
        if "Tiered Startup" not in content:
            content += "\n" + startup_text
            path.write_text(content)
    else:
        path.write_text(f"# {platform['name']} Instructions\n{startup_text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Non-interactive mode
    if "--non-interactive" in sys.argv:
        print("Non-interactive mode not yet implemented. Use interactive wizard.")
        sys.exit(1)

    banner()

    platform = step_platform()
    store = step_store()
    level = step_level()
    project = step_project()

    print(f"\n{'=' * 60}")
    print("  Review your choices:")
    print(f"{'=' * 60}")
    print(f"  Platform:        {platform['name']}")
    print(f"  Data store:      {store['name']}")
    print(f"  Level:           {level} — {LEVELS[level]}")
    print(f"  Project:         {project['name']} ({project['dir']})")
    print(f"  AH rules:        {'Yes' if project['include_ah_rules'] else 'No'}")
    print(f"  Backlog:         {'Yes' if project['include_backlog'] else 'No'}")
    print(f"  Hooks dir:       {platform['hooks_dir']}")
    print(f"  Settings file:   {platform['settings_file']}")
    print(f"  Instructions:    {platform['instructions_file']}")

    if not confirm("\nProceed with setup?"):
        print("Setup cancelled.")
        sys.exit(0)

    generate(platform, store, level, project)


if __name__ == "__main__":
    main()
