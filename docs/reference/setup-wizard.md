# Setup Wizard

The fastest way to get started. Run the interactive wizard and it handles everything.

## Quick Start

```bash
git clone https://github.com/dexmaddy/agentic-ai-tiered-startup.git
cd agentic-ai-tiered-startup
python3 setup.py
```

## What the Wizard Does

1. **Asks your platform** — Claude Code, Cursor, Windsurf, Aider, or custom
2. **Asks your data store** — YAML/JSON files, SQLite, or PostgreSQL
3. **Asks your enforcement level** — Level 1 (manifest only) through Level 4 (full architecture)
4. **Asks project details** — anti-hallucination rules, persistent backlog

Then it:

- Copies the right hook scripts to your project
- Generates config files for your chosen data store
- Creates sample rules you can customize
- Wires the settings file for your agent platform
- Installs any needed dependencies

## Non-Interactive Mode

For CI/CD or scripted setup:

```bash
python3 setup.py --non-interactive \
  --platform claude \
  --store sqlite \
  --level 2 \
  --dir /path/to/your/project
```

### Options

| Flag | Values | Default |
|------|--------|---------|
| `--platform` | `claude`, `cursor`, `windsurf`, `aider`, `custom` | `claude` |
| `--store` | `yaml`, `sqlite`, `postgres` | `yaml` |
| `--level` | `1`, `2`, `3`, `4` | `2` |
| `--dir` | path to project | current directory |
| `--no-ah-rules` | skip anti-hallucination rules | included by default |
| `--no-backlog` | skip persistent backlog | included by default |

## DB-Mode Features

When you choose **SQLite** or **PostgreSQL** as your data store, the setup
wizard configures additional features that activate automatically via the
`AGENT_DB_PATH` environment variable:

| Feature | What It Does |
|---------|-------------|
| **Edit logging** | Every Write/Edit operation is logged to the `rule_log` table via `on_edit.py` |
| **Session summary enforcement** | `on_stop.py` requires a `session_summaries` row before allowing exit |
| **Stale fact detection** | `gate_check.py` warns when `system_facts` or `fact_references` contain stale entries |

These require three additional tables in your database:

| Table | Purpose |
|-------|---------|
| `rule_log` | Tracks every file edit with timestamp, path, and hook source |
| `system_facts` | Stores project facts (counts, paths, versions) that other rules reference |
| `fact_references` | Maps which rules depend on which facts, enabling staleness detection |

No extra configuration is needed — setting `AGENT_DB_PATH` to your database
file path enables all three features automatically.

## Level 4 Stop Hook Config

At Level 4, the wizard generates a stop hook config with these options:

```yaml
stop:
  require_clean_repos: true
  require_audit_pass: true
  require_session_summary: true     # DB mode only
  shutdown_steps:                   # custom checks (same validators as startup)
    - name: lint-clean
      command: "npm run lint 2>&1 | tail -1"
      validator: "contains:no errors"
      fail_message: "Linter has errors"
```

`shutdown_steps` uses the same validator framework as startup checks.
`require_session_summary` only applies when `AGENT_DB_PATH` is set.
