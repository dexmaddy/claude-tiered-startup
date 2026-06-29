#!/usr/bin/env python3
"""SessionStart hook (Database variant): read rules from SQLite, generate tier files.

Method B of the Agentic AI Tiered Startup Architecture.
Use this instead of on_session_start.py when your rules, backlog, and session
state live in a SQLite database rather than YAML config files.

Requires: SQLite database with these tables:
  - rules (id, name, content, category, tier, triggers, active)
  - checks (id, name, command, validator, fail_message, optional)
  - backlog (id, item, status, priority, category, created_at, completed_at)
  - session_summaries (id, topic, completed_items, next_items, session_date)
  - config (key, value) — for gates, stop, cross_check settings

Setup:
  1. Run: python3 hooks/on_session_start_db.py --init-db project.db
     This creates all tables with the schema above.
  2. Populate rules: INSERT INTO rules (name, content, category, tier) VALUES (...)
  3. Update settings.json to point to this script instead of on_session_start.py

Environment:
  AGENT_DB_PATH — path to SQLite database (default: project.db)
  CLAUDE_SESSION_ID — session identifier (default: "default")
"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "default")
TMPDIR = tempfile.gettempdir()
DB_PATH = os.environ.get("AGENT_DB_PATH", "project.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create all tables for the tiered startup system."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            tier INTEGER DEFAULT 1,              -- 1 = always load, 2 = on-demand
            triggers TEXT,                        -- JSON array of trigger keywords (tier 2 only)
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            validator TEXT DEFAULT 'empty_output',
            fail_message TEXT,
            optional INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS backlog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            status TEXT DEFAULT 'active',          -- active, completed, deferred
            priority INTEGER DEFAULT 3,            -- 1 (highest) to 5 (lowest)
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS session_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            completed_items TEXT,                   -- JSON array
            next_items TEXT,                        -- JSON array
            session_date DATE DEFAULT CURRENT_DATE,
            duration_minutes INTEGER,
            prompt_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL                     -- JSON-encoded value
        );
    """)
    # Insert default config if empty
    defaults = {
        "gates.block_until_tier1": "true",
        "gates.tier2_keyword_scan": "true",
        "gates.keyword_scan_fields": '["command", "file_path", "prompt", "description"]',
        "gates.keyword_scan_max_chars": "120",
        "gates.prompt_health_warnings": "[40, 60, 80]",
        "stop.require_clean_repos": "true",
        "stop.require_transcript": "false",
        "stop.max_retries": "8",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")
    print(f"Tables: rules, checks, backlog, session_summaries, config")
    print(f"\nNext steps:")
    print(f"  1. Add rules:  sqlite3 {db_path} \"INSERT INTO rules (name, content, category, tier) VALUES ('my-rule', 'Rule content here', 'general', 1)\"")
    print(f"  2. Add checks: sqlite3 {db_path} \"INSERT INTO checks (name, command, validator) VALUES ('git-clean', 'git status --porcelain', 'empty_output')\"")
    print(f"  3. Update settings.json to use: python3 .agent/hooks/on_session_start_db.py")


def get_config(conn: sqlite3.Connection) -> dict:
    """Read config table into nested dict."""
    config: dict = {}
    for row in conn.execute("SELECT key, value FROM config"):
        keys = row["key"].split(".")
        d = config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        try:
            d[keys[-1]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            d[keys[-1]] = row["value"]
    return config


def run_checks(conn: sqlite3.Connection) -> list[dict]:
    """Run infrastructure checks from the checks table."""
    from validators import get_validator, validate_exit_code

    results = []
    for row in conn.execute("SELECT * FROM checks WHERE active = 1"):
        name = row["name"]
        try:
            proc = subprocess.run(
                row["command"], shell=True, capture_output=True, text=True, timeout=30
            )
            validator_spec = row["validator"]
            if validator_spec:
                passed, detail = get_validator(validator_spec)(proc.stdout)
            else:
                passed, detail = validate_exit_code(proc.returncode, proc.stdout)
        except subprocess.TimeoutExpired:
            passed, detail = False, "timeout after 30s"
        except Exception as e:
            passed, detail = False, str(e)

        status = "OK" if passed else ("WARN" if row["optional"] else "FAIL")
        results.append({"name": name, "status": status, "detail": detail})
    return results


def generate_tier1_files(conn: sqlite3.Connection, check_results: list[dict]) -> list[dict]:
    """Generate tier1 files from DB rules + infra report + backlog."""
    entries = []

    # Infra report
    infra_path = os.path.join(TMPDIR, f"tier1-infra-report-{SESSION_ID}.md")
    lines = ["# Infrastructure Report", f"Time: {__import__('datetime').datetime.now():%Y-%m-%d %H:%M}", ""]
    for r in check_results:
        lines.append(f"- [{r['status']}] {r['name']}: {r['detail']}")
    ok = sum(1 for r in check_results if r["status"] == "OK")
    fail = sum(1 for r in check_results if r["status"] == "FAIL")
    lines.append(f"\n**Result: {ok} OK, {fail} FAIL**")
    Path(infra_path).write_text("\n".join(lines))
    entries.append({"name": "infra-report", "path": infra_path,
                    "lines": len(lines), "source": "checks table"})

    # Tier 1 rules grouped by category
    categories: dict[str, list] = {}
    for row in conn.execute("SELECT * FROM rules WHERE tier = 1 AND active = 1 ORDER BY category, name"):
        categories.setdefault(row["category"], []).append(row)

    for category, rules in categories.items():
        cat_path = os.path.join(TMPDIR, f"tier1-{category}-{SESSION_ID}.md")
        lines = [f"# Rules: {category}", f"Count: {len(rules)}", ""]
        for rule in rules:
            lines.append(f"## {rule['name']}")
            lines.append("")
            lines.append(rule["content"])
            lines.append("")
        Path(cat_path).write_text("\n".join(lines))
        entries.append({"name": category, "path": cat_path,
                        "lines": len(lines), "source": f"rules WHERE category='{category}'"})

    # Backlog + session continuity
    backlog_path = os.path.join(TMPDIR, f"tier1-backlog-{SESSION_ID}.md")
    lines = ["# Active Backlog", ""]
    for row in conn.execute("SELECT * FROM backlog WHERE status = 'active' ORDER BY priority"):
        lines.append(f"- [{row['category'] or 'task'}] {row['item']} (priority {row['priority']})")

    lines.append("")
    lines.append("## Continue From Last Session")
    lines.append("")
    last = conn.execute("SELECT * FROM session_summaries ORDER BY id DESC LIMIT 1").fetchone()
    if last:
        lines.append(f"Topic: {last['topic'] or 'unknown'}")
        if last["completed_items"]:
            lines.append("Completed:")
            for item in json.loads(last["completed_items"]):
                lines.append(f"  - {item}")
        if last["next_items"]:
            lines.append("Next items:")
            for item in json.loads(last["next_items"]):
                lines.append(f"  - {item}")
    else:
        lines.append("No previous session recorded.")

    Path(backlog_path).write_text("\n".join(lines))
    entries.append({"name": "backlog", "path": backlog_path,
                    "lines": len(lines), "source": "backlog + session_summaries"})

    return entries


def get_tier2_defs(conn: sqlite3.Connection) -> list[dict]:
    """Get tier2 rule definitions with triggers."""
    defs = []
    for row in conn.execute("SELECT name, triggers, category FROM rules WHERE tier = 2 AND active = 1"):
        triggers = json.loads(row["triggers"]) if row["triggers"] else []
        defs.append({
            "name": row["name"],
            "triggers": triggers,
            "source": f"rules WHERE name='{row['name']}'",
            "description": f"Tier 2: {row['category']}",
        })
    return defs


def write_manifest(tier1: list[dict], tier2: list[dict], config: dict) -> str:
    manifest_path = os.path.join(TMPDIR, f"manifest-{SESSION_ID}.json")
    manifest = {
        "session_id": SESSION_ID,
        "tier1": tier1,
        "tier2": tier2,
        "gates": config.get("gates", {}),
        "stop": config.get("stop", {}),
        "cross_check": config.get("cross_check", {}),
    }
    Path(manifest_path).write_text(json.dumps(manifest, indent=2))
    return manifest_path


def write_sentinel() -> None:
    sentinel_path = os.path.join(TMPDIR, f"startup-complete-{SESSION_ID}.json")
    Path(sentinel_path).write_text(json.dumps({
        "session_id": SESSION_ID,
        "stage": "tier1_pending",
        "completed_reads": [],
        "cross_check_done": False,
    }, indent=2))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--init-db":
        db_path = sys.argv[2] if len(sys.argv) > 2 else "project.db"
        init_db(db_path)
        sys.exit(0)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        print(f"Run: python3 {__file__} --init-db {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = get_db()
    config = get_config(conn)

    check_results = run_checks(conn)
    tier1_entries = generate_tier1_files(conn, check_results)
    tier2_defs = get_tier2_defs(conn)

    manifest_path = write_manifest(tier1_entries, tier2_defs, config)
    write_sentinel()

    ok = sum(1 for r in check_results if r["status"] == "OK")
    fail = sum(1 for r in check_results if r["status"] == "FAIL")
    total_lines = sum(e["lines"] for e in tier1_entries)

    print(f"STARTUP (DB): {ok} OK, {fail} FAIL")
    print(f"Manifest: {manifest_path}")
    print(f"Tier 1: {len(tier1_entries)} files ({total_lines} lines)")
    print(f"Tier 2: {len(tier2_defs)} rules (on-demand)")
    print("ACTION REQUIRED: Read manifest, then read all Tier 1 files.")
    for e in tier1_entries:
        print(f"  - {e['path']} ({e['lines']} lines, {e['name']})")

    conn.close()


if __name__ == "__main__":
    main()
