# Session Continuity: Persistent Backlog + Session Handoff

AI agent sessions are ephemeral — when a session ends, the agent's
task list, progress, and "what's next" disappear. The next session
starts from zero, with no memory of what was in progress.

This guide adds two features to solve this:

1. **Persistent Backlog** — todos survive across sessions
2. **Session Handoff** — each session knows what the last session was doing

---

## The Problem

Most AI coding agents have a session-only task list (like Claude Code's
TodoWrite). When the session ends:

- Active tasks vanish — no record they existed
- The user has to re-explain what they were working on
- Priorities decided in one session are lost in the next
- "Pin this for later" has no "later" to land in

**The fix:** Store tasks in a persistent file or database that the
startup hook loads into Tier 1 every session.

---

## Method A: JSON File (Simple, No Dependencies)

### Setup

Create `backlog.json` in your project root:

```json
{
  "tasks": [
    {
      "id": 1,
      "item": "Add input validation to the signup form",
      "status": "active",
      "priority": 1,
      "category": "feature",
      "created": "2026-06-29"
    },
    {
      "id": 2,
      "item": "Fix flaky test in auth module",
      "status": "active",
      "priority": 2,
      "category": "bug",
      "created": "2026-06-28"
    }
  ],
  "last_session": {
    "topic": "Auth module refactor",
    "completed": ["Extracted JWT logic to separate module", "Added unit tests"],
    "next_items": ["Fix flaky test", "Update API docs"],
    "date": "2026-06-29"
  }
}
```

### Wire into Startup Config

Add a generated tier1 file that reads the backlog:

```yaml
tiers:
  tier1:
    - name: backlog
      source: scripts/gen_backlog.sh
      type: generated
      description: "Active tasks and session continuity"
```

Create `scripts/gen_backlog.sh`:

```bash
#!/bin/bash
python3 -c "
import json, sys
try:
    data = json.load(open('backlog.json'))
except FileNotFoundError:
    print('# No backlog found'); sys.exit(0)

print('# Active Backlog')
print()
active = [t for t in data.get('tasks', []) if t['status'] == 'active']
active.sort(key=lambda t: t.get('priority', 99))
for t in active:
    print(f\"- [{t.get('category','task')}] {t['item']} (priority {t.get('priority', '-')})\")
print()

last = data.get('last_session', {})
if last:
    print('## Continue From Last Session')
    print()
    print(f\"Topic: {last.get('topic', 'unknown')}\")
    if last.get('completed'):
        print('Completed:')
        for c in last['completed']:
            print(f'  - {c}')
    if last.get('next_items'):
        print('Next items:')
        for n in last['next_items']:
            print(f'  - {n}')
"
```

### How to Use

**Adding tasks** — tell your agent:
> "Add to backlog: implement rate limiting for the API"

The agent updates `backlog.json`:
```python
import json
data = json.load(open("backlog.json"))
new_id = max((t["id"] for t in data["tasks"]), default=0) + 1
data["tasks"].append({
    "id": new_id,
    "item": "Implement rate limiting for the API",
    "status": "active",
    "priority": 2,
    "category": "feature",
    "created": "2026-06-30"
})
json.dump(data, open("backlog.json", "w"), indent=2)
```

**Completing tasks:**
```python
for t in data["tasks"]:
    if t["id"] == 1:
        t["status"] = "completed"
```

**Session handoff** — at the end of each session, the agent updates
`last_session` with what was done and what's next. The startup hook
reads this into Tier 1, so the next session starts with full context.

### Agent Instructions

Add to your agent instructions file:

```markdown
## Task Persistence

When the user says "add to todo", "pin for later", "save for next session",
or any task persistence request — update backlog.json, NOT the session-only
task list. The session task list disappears when the session ends.

Before ending a session, update backlog.json last_session with:
- topic: what was the main focus
- completed: what got done
- next_items: what should happen next
```

---

## Method B: SQLite Database (Scalable, Queryable)

When your backlog grows beyond ~20 items, or you need to search by
category, track completion dates, or generate reports, graduate to SQLite.

### Setup

Create the table:

```sql
CREATE TABLE IF NOT EXISTS backlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- active, completed, deferred
    priority INTEGER DEFAULT 3,    -- 1 (highest) to 5 (lowest)
    category TEXT,                 -- feature, bug, research, infra
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT,
    completed_items TEXT,          -- JSON array
    next_items TEXT,               -- JSON array
    session_date DATE DEFAULT CURRENT_DATE,
    duration_minutes INTEGER,
    prompt_count INTEGER
);
```

### Wire into Startup Config

```yaml
tiers:
  tier1:
    - name: backlog
      source: scripts/gen_backlog_db.sh
      type: generated
      description: "Active tasks and session continuity from DB"
```

Create `scripts/gen_backlog_db.sh`:

```bash
#!/bin/bash
DB="project.db"

echo "# Active Backlog"
echo ""
sqlite3 "$DB" "SELECT '- [' || category || '] ' || item || ' (priority ' || priority || ')' FROM backlog WHERE status='active' ORDER BY priority"
echo ""

echo "## Continue From Last Session"
echo ""
sqlite3 "$DB" "SELECT 'Topic: ' || topic FROM session_summaries ORDER BY id DESC LIMIT 1"
sqlite3 "$DB" "SELECT 'Next: ' || value FROM session_summaries, json_each(session_summaries.next_items) ORDER BY session_summaries.id DESC LIMIT 5"
```

### Why SQLite Over JSON

| Need | JSON | SQLite |
|------|------|--------|
| Under 20 tasks | Works fine | Overkill |
| Search by category | Load + filter in Python | `WHERE category = 'bug'` |
| Track completion dates | Manual timestamp | `completed_at TIMESTAMP` |
| Concurrent agent sessions | Risk of corruption | WAL mode handles it |
| History / reporting | Grows unwieldy | `SELECT COUNT(*) GROUP BY category` |
| Cross-referencing tasks with rules | Impossible | JOIN across tables |

**Graduation signal:** When you find yourself writing Python to filter
and sort your JSON backlog, it's time for SQLite.

---

## Session Handoff Pattern

The session handoff works the same regardless of storage method:

```
Session N ends:
  1. Agent writes what was done (completed items)
  2. Agent writes what's next (pending items)
  3. Saves to backlog.json or session_summaries table

Session N+1 starts:
  1. SessionStart hook reads backlog + last session
  2. Generates a "Continue From Last Session" section
  3. Loads it as part of Tier 1
  4. Agent sees: "Last session worked on X. Next items: A, B, C"
  5. Agent picks up where the last session left off
```

### What to Capture in Session Handoff

| Field | Purpose | Example |
|-------|---------|---------|
| `topic` | One-line summary of main focus | "Auth module refactor" |
| `completed` | What got done (bullet list) | ["Extracted JWT logic", "Added tests"] |
| `next_items` | What should happen next | ["Fix flaky test", "Update docs"] |
| `date` | When the session happened | "2026-06-29" |
| `prompt_count` | How many prompts (context health) | 45 |

### Stop Hook Integration

Wire session handoff into the stop hook so it happens automatically:

```yaml
stop:
  require_clean_repos: true
  require_session_handoff: true   # Add this
```

The stop hook checks if `last_session` was updated. If not, it blocks
exit (exit code 2) and tells the agent to save session state first.

---

## Quick Start Checklist

For JSON method:
- [ ] Create `backlog.json` with the template above
- [ ] Create `scripts/gen_backlog.sh`
- [ ] Add the `backlog` tier1 entry to `startup-config.yaml`
- [ ] Add task persistence instructions to your agent instructions file
- [ ] Test: start a session, verify backlog appears in tier1 output

For SQLite method:
- [ ] Create the tables with the SQL above
- [ ] Create `scripts/gen_backlog_db.sh`
- [ ] Add the `backlog` tier1 entry to `startup-config.yaml`
- [ ] Test: `sqlite3 project.db "SELECT * FROM backlog"` shows your tasks
