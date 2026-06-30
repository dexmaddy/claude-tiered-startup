#!/usr/bin/env python3
"""SessionStart hook (Database variant): read rules from SQLite or PostgreSQL.

Method B of the AI Agent Harness.
Use this instead of on_session_start.py when your rules, backlog, and session
state live in a database rather than YAML config files.

Supports:
  - SQLite: AGENT_DB_PATH=project.db (default, zero dependencies)
  - PostgreSQL: AGENT_DB_PATH=postgresql://user:pass@host/db (requires psycopg2)

The script auto-detects which backend to use based on the connection string.

Requires these tables (created by --init-db):
  - rules (id, name, content, category, tier, triggers, active)
  - checks (id, name, command, validator, fail_message, optional)
  - backlog (id, item, status, priority, category, created_at, completed_at)
  - session_summaries (id, topic, completed_items, next_items, session_date)
  - config (key, value) — for gates, stop, cross_check settings

Setup:
  SQLite:     python3 hooks/on_session_start_db.py --init-db project.db
  PostgreSQL: python3 hooks/on_session_start_db.py --init-db postgresql://user:pass@host/db

Environment:
  AGENT_DB_PATH — SQLite file path or PostgreSQL connection string (default: project.db)
  CLAUDE_SESSION_ID — session identifier (default: "default")
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
DB_PATH = os.environ.get("AGENT_DB_PATH", "project.db")

# DB-API 2.0 placeholder: ? for sqlite3, %s for psycopg2
PH = "?"


def _is_postgres(path: str) -> bool:
    return path.startswith("postgresql://") or path.startswith("postgres://")


def get_db():
    """Connect to SQLite or PostgreSQL based on AGENT_DB_PATH."""
    global PH
    if _is_postgres(DB_PATH):
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            print("ERROR: psycopg2 required for PostgreSQL. Install: pip install psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        PH = "%s"
        conn = psycopg2.connect(DB_PATH)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        import sqlite3
        PH = "?"
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _execute_schema(conn, schema_sql: str) -> None:
    """Execute schema DDL — handles sqlite3.executescript vs psycopg2 execute."""
    if _is_postgres(DB_PATH):
        conn.cursor().execute(schema_sql)
        conn.commit()
    else:
        conn.executescript(schema_sql)


def init_db(db_path: str) -> None:
    """Create all tables for the AI Agent Harness."""
    if _is_postgres(db_path):
        try:
            import psycopg2
        except ImportError:
            print("ERROR: psycopg2 required. Install: pip install psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        conn = psycopg2.connect(db_path)
    else:
        import sqlite3
        conn = sqlite3.connect(db_path)

    serial_type = "SERIAL" if _is_postgres(db_path) else "INTEGER"
    auto_increment = "" if _is_postgres(db_path) else "AUTOINCREMENT"
    timestamp_default = "NOW()" if _is_postgres(db_path) else "CURRENT_TIMESTAMP"

    schema = f"""
        CREATE TABLE IF NOT EXISTS rules (
            id {serial_type} PRIMARY KEY {auto_increment},
            name TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            tier INTEGER DEFAULT 1,
            triggers TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT {timestamp_default},
            updated_at TIMESTAMP DEFAULT {timestamp_default}
        );

        CREATE TABLE IF NOT EXISTS checks (
            id {serial_type} PRIMARY KEY {auto_increment},
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            validator TEXT DEFAULT 'empty_output',
            fail_message TEXT,
            optional INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS backlog (
            id {serial_type} PRIMARY KEY {auto_increment},
            item TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            priority INTEGER DEFAULT 3,
            category TEXT,
            created_at TIMESTAMP DEFAULT {timestamp_default},
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS session_summaries (
            id {serial_type} PRIMARY KEY {auto_increment},
            topic TEXT,
            completed_items TEXT,
            next_items TEXT,
            session_date DATE DEFAULT CURRENT_DATE,
            duration_minutes INTEGER,
            prompt_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rule_log (
            id {serial_type} PRIMARY KEY {auto_increment},
            event_type TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT,
            session_id TEXT,
            logged_at TIMESTAMP DEFAULT {timestamp_default}
        );

        CREATE TABLE IF NOT EXISTS system_facts (
            fact_key TEXT PRIMARY KEY,
            fact_value TEXT NOT NULL,
            display_forms TEXT DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT {timestamp_default}
        );

        CREATE TABLE IF NOT EXISTS fact_references (
            id {serial_type} PRIMARY KEY {auto_increment},
            fact_key TEXT NOT NULL,
            file_name TEXT NOT NULL
        );
    """
    _execute_schema(conn, schema)
    # Insert default config if empty
    defaults = {
        "gates.block_until_tier1": "true",
        "gates.tier2_keyword_scan": "true",
        "gates.keyword_scan_fields": '["command", "file_path", "prompt", "description"]',
        "gates.keyword_scan_max_chars": "120",
        "gates.prompt_health_warnings": "[40, 60, 80]",
        "stop.require_clean_repos": "true",
        "stop.require_transcript": "false",
        "stop.require_session_summary": "true",
        "stop.max_retries": "8",
    }
    ph = "%s" if _is_postgres(db_path) else "?"
    upsert = "ON CONFLICT (key) DO NOTHING" if _is_postgres(db_path) else "OR IGNORE"
    cur = conn.cursor()
    for key, value in defaults.items():
        cur.execute(
            f"INSERT {upsert} INTO config (key, value) VALUES ({ph}, {ph})", (key, value)
        )
    conn.commit()
    conn.close()
    is_pg = _is_postgres(db_path)
    print(f"Database initialized: {db_path}")
    print(f"Backend: {'PostgreSQL' if is_pg else 'SQLite'}")
    print(f"Tables: rules, checks, backlog, session_summaries, config, rule_log, system_facts, fact_references")
    if is_pg:
        print(f"\nNext steps:")
        print(f"  1. Add rules:  psql {db_path} -c \"INSERT INTO rules (name, content, category, tier) VALUES ('my-rule', 'Rule content here', 'general', 1)\"")
        print(f"  2. Add checks: psql {db_path} -c \"INSERT INTO checks (name, command, validator) VALUES ('git-clean', 'git status --porcelain', 'empty_output')\"")
        print(f"  3. Set: export AGENT_DB_PATH={db_path}")
    else:
        print(f"\nNext steps:")
        print(f"  1. Add rules:  sqlite3 {db_path} \"INSERT INTO rules (name, content, category, tier) VALUES ('my-rule', 'Rule content here', 'general', 1)\"")
        print(f"  2. Add checks: sqlite3 {db_path} \"INSERT INTO checks (name, command, validator) VALUES ('git-clean', 'git status --porcelain', 'empty_output')\"")
        print(f"  3. Update settings.json to use: python3 .agent/hooks/on_session_start_db.py")


def get_config(conn) -> dict:
    """Read config table into nested dict."""
    config: dict = {}
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    for row in cur:
        keys = row["key"].split(".")
        d = config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        try:
            d[keys[-1]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            d[keys[-1]] = row["value"]
    return config


def run_checks(conn) -> list[dict]:
    """Run infrastructure checks from the checks table."""
    from validators import get_validator, validate_exit_code

    results = []
    cur = conn.cursor()
    cur.execute("SELECT * FROM checks WHERE active = 1")
    for row in cur:
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


def generate_tier1_files(conn, check_results: list[dict]) -> list[dict]:
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
    cur = conn.cursor()
    cur.execute("SELECT * FROM rules WHERE tier = 1 AND active = 1 ORDER BY category, name")
    for row in cur:
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
    cur2 = conn.cursor()
    cur2.execute("SELECT * FROM backlog WHERE status = 'active' ORDER BY priority")
    for row in cur2:
        lines.append(f"- [{row['category'] or 'task'}] {row['item']} (priority {row['priority']})")

    lines.append("")
    lines.append("## Continue From Last Session")
    lines.append("")
    cur3 = conn.cursor()
    cur3.execute("SELECT * FROM session_summaries ORDER BY id DESC LIMIT 1")
    last = cur3.fetchone()
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


def get_tier2_defs(conn) -> list[dict]:
    """Get tier2 rule definitions with triggers."""
    defs = []
    cur = conn.cursor()
    cur.execute("SELECT name, triggers, category FROM rules WHERE tier = 2 AND active = 1")
    for row in cur:
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
