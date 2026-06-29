# Data Store & Platform Guide

## Data Source: Files First, Database When You Graduate

This project uses **YAML config + markdown rule files** by default. No database
required to get started. This is intentional — for most users, flat files are
the right choice.

**When files work (under ~50 rules):**
- Editable with any text editor, no CLI needed
- Full git history for free
- Easy to read, review, and onboard new team members
- Zero dependencies beyond PyYAML

**When to graduate to a database (~50+ rules):**

| Pain Signal | What's Happening | DB Solution |
|-------------|-----------------|-------------|
| "Which rules reference fact X?" | Cross-referencing requires scanning every file | One JOIN query |
| Drift detection is fragile | `find + wc -l` pipelines break on edge cases | `SELECT COUNT(*)` is atomic |
| Concurrent agent sessions corrupt state | Two agents edit the same YAML simultaneously | SQLite WAL mode handles concurrent writes |
| Rule search is slow | Grep across 20+ files to find a category | Indexed query by category/trigger |
| Can't track when rules were added/changed | Git log works but is coarse | `created_at`, `updated_at` columns |

**Recommended graduation path:**
1. Start with YAML (this project's default)
2. Watch for the pain signals above
3. When they appear, migrate to SQLite (single file, no server, Python stdlib)
4. Build a thin CLI wrapper so you never need raw SQL

SQLite is recommended over Postgres/MySQL because it's embedded (no server),
the DB is a single portable file (same as YAML), and it ships with Python.
LangChain and CrewAI both use SQLite for persistent agent state.

---

## Platform Compatibility

The **concepts** (tiered loading, gating, drift detection, anti-hallucination
rules) apply to any AI agent system. The **reference implementation** uses
Claude Code's hooks API, but the patterns adapt to any platform with lifecycle events.

| Platform | How to Adapt |
|----------|-------------|
| **Claude Code** | Use as-is — hooks map directly to SessionStart, PreToolUse, etc. |
| **Cursor** | Use `.cursor/rules/` for tier1 rules, `@rules` for tier2. Gate via custom commands. |
| **Windsurf** | Use `.windsurfrules` for rules, Cascade memories for tier state tracking. |
| **Aider** | Use `.aider.conf.yml` conventions + `--read` flag for tier1 loading at startup. |
| **Continue.dev** | Use `.continuerc.json` context providers for tiered rule loading. |
| **Custom agents** | Implement the hook pattern as middleware in your agent loop — check state before tool execution. |
| **LangChain/CrewAI** | Add a startup node/task that loads rules, a gate callback that checks sentinel before tool use. |

**The core pattern is framework-agnostic:**
1. **Before session work:** load essential context (tier1)
2. **Before each tool call:** verify context is loaded, trigger on-demand loading (tier2)
3. **After each modification:** sync state, check for drift
4. **Before session end:** verify cleanup

## Two Deployment Methods

| | Method A: YAML Config | Method B: SQLite Database |
|---|---|---|
| **Script** | `on_session_start.py` | `on_session_start_db.py` |
| **Rules stored in** | Markdown files on disk | `rules` table in SQLite |
| **Backlog** | `backlog.json` | `backlog` table |
| **Session handoff** | JSON file | `session_summaries` table |
| **Config** | `startup-config.yaml` | `config` table |
| **Dependencies** | PyYAML | None (sqlite3 is Python stdlib) |
| **Best for** | Under ~50 rules, single user | 50+ rules, cross-referencing, concurrent sessions |
| **Setup** | Copy config, write markdown files | `python3 hooks/on_session_start_db.py --init-db project.db` |

Start with Method A. Graduate to Method B when you hit the
[pain signals](../reference/session-continuity.md) described
in the data source guide.
