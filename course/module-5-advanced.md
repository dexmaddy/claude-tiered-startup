---
layout: default
title: "Module 5: Advanced Features"
parent: Course
nav_order: 5
---

# Module 5: On-Demand Loading & Drift Detection

**Time:** 20 minutes
**Goal:** Add tier2 keyword triggers, cross-check drift detection,
PostToolUse actions, and the stop hook.

---

## Part A: Tier 2 On-Demand Loading

### The Concept

Tier 2 files load only when the agent's tool calls contain matching keywords.
This keeps specialized rules out of the context window until they're needed.

### Step 1: Define Tier 2 Rules

Add to `startup-config.yaml`:

```yaml
tiers:
  tier2:
    - name: deploy-rules
      triggers: ["deploy", "release", "production", "staging"]
      source: rules/deploy-rules.md
      description: "Deployment procedures"

    - name: api-rules
      triggers: ["api", "endpoint", "REST", "swagger"]
      source: rules/api-rules.md
      description: "API design standards"
```

Create the corresponding rule files in `rules/`.

### Step 2: Enable Keyword Scanning

```yaml
gates:
  block_until_tier1: true
  tier2_keyword_scan: true          # ← Enable
  keyword_scan_fields:
    - command
    - file_path
    - prompt
    - description
  keyword_scan_max_chars: 120
```

### Step 3: Test It

Start a session, complete tier1 loading, then:

```
You: deploy the app to staging
```

the agent tries to run a Bash command containing "deploy" → gate scans
the command text → finds "deploy" matches the deploy-rules trigger →
blocks with:

```
Tier 2 files triggered — read before proceeding:
  - deploy-rules: rules/deploy-rules.md
```

the agent reads the file, then the next tool call is allowed.

### False Positive Prevention

Keyword scanning is limited to prevent accidental triggers:

1. **Only specific fields** — scans `command`, `file_path`, `prompt`,
   `description`. Does NOT scan the full JSON (which might contain
   unrelated data in arguments).

2. **First N characters only** — default 120 chars. A long file being
   written won't trigger just because the content mentions "deploy".

3. **Already-loaded files skip** — once the agent reads a tier2 file,
   that trigger won't fire again in the same session.

**Tip:** If you get false positives, make triggers more specific:
- Bad: `["test"]` (fires on "test", "testing", "latest")
- Better: `["run tests", "test suite", "pytest", "jest"]`

---

## Part B: Cross-Check Drift Detection

### The Concept

After tier1 loads, run a one-time check comparing expected state
(from your config) against actual state (from live commands). This
catches drift that would otherwise go unnoticed.

### Step 1: Define Expectations

Add to `startup-config.yaml`:

```yaml
cross_check:
  expected_counts:
    rule_file_count:
      command: "find rules/ -name '*.md' | wc -l | tr -d ' '"
      expected: 3
      auto_heal: false

    test_count:
      command: "find tests/ -name 'test_*.py' | wc -l | tr -d ' '"
      expected: 12
      auto_heal: false
```

### Step 2: How It Runs

The gate_check.py script automatically invokes cross_check.py after
tier1 completes — once per session:

1. **Pass 1:** Run each command, compare output to expected value
2. **Auto-heal** safe items (if configured with `auto_heal: true`)
3. **Pass 2:** Re-check healed items to confirm the fix worked
4. **Stop** — no more passes (bounded, prevents infinite loops)

Results are logged to the sentinel and reported:

```
Cross-check: 2/2 passed
```

Or if drift is found:

```
Cross-check: 1/2 passed, 1 DRIFTED
  DRIFT: rule_file_count: expected 3, got 5
```

### When to Use Auto-Heal

- **Safe:** Updating a count in a config file
- **Unsafe:** Deleting files, modifying code, running migrations
- **Rule:** If the fix could cause damage, set `auto_heal: false`
  and let the human decide

---

## Part C: PostToolUse Hook

### The Concept

After every Write or Edit, run automated actions:
- Sync important files to backup locations
- Track edit count for save reminders
- Detect stale references (advanced)

### Setup

```bash
cp path/to/agentic-ai-tiered-startup/hooks/on_edit.py .agent/hooks/
```

Add to `.agent/settings.json`:

```json
"PostToolUse": [
  {
    "matcher": "Write|Edit",
    "hooks": [{
      "type": "command",
      "command": "python3 .agent/hooks/on_edit.py",
      "timeout": 5000
    }]
  }
]
```

The default on_edit.py provides periodic save reminders (every 15 edits).
Customize it to add file sync or other post-write actions.

---

## Part D: Stop Hook

### The Concept

Block session exit until cleanup is done. The stop hook returns exit
code 2 (retry) when checks fail, giving Claude a chance to fix the
issue. After max retries, it exits cleanly.

### Setup

```bash
cp path/to/agentic-ai-tiered-startup/hooks/on_stop.py .agent/hooks/
```

Add to config:

```yaml
stop:
  require_clean_repos: true
  require_transcript: false
  max_retries: 8
```

Wire in settings:

```json
"Stop": [
  {
    "matcher": "",
    "hooks": [{
      "type": "command",
      "command": "python3 .agent/hooks/on_stop.py",
      "timeout": 10000
    }]
  }
]
```

### How Retries Work

```
Session ending
       │
       v
on_stop.py checks repos
       │
       ├── Clean? → exit 0 (allow exit)
       └── Dirty? → exit 2 (retry)
                     │
                     v
               the agent sees: "Repos not clean: 3 uncommitted files"
               Claude runs: git add + git commit
                     │
                     v
               on_stop.py runs again
               Clean now? → exit 0 ✓
```

Max retries prevents the user from being trapped if the check can't
be satisfied.

---

## What You've Built (Full Level 4)

```
Session start → SessionStart hook
  → Checks infrastructure
  → Generates tier1 + tier2 files
  → Writes manifest + sentinel
       │
Every user message → UserPromptSubmit hook
  → Blocks until tier1 complete
  → Warns at prompt thresholds
       │
Every tool call → PreToolUse hook
  → Blocks non-Read until tier1 complete
  → Runs cross-check once
  → Triggers tier2 on keywords
       │
Every Write/Edit → PostToolUse hook
  → Save reminders
  → File sync (if configured)
       │
Session end → Stop hook
  → Blocks until repos clean
  → Retries up to N times
```

---

## Part E: Session Continuity

Agent sessions are ephemeral — tasks, progress, and "what's next"
vanish when the session ends. Session continuity solves this with
two features:

1. **Persistent Backlog** — todos stored in a file or database that
   survives across sessions, loaded into Tier 1 at startup
2. **Session Handoff** — each session records what was done and what's
   next, so the following session picks up where the last one left off

**Why this matters:** Without continuity, users re-explain context
every session. With it, the agent says "Last session worked on auth
refactor. Next items: fix flaky test, update docs" — and starts working.

Two implementation methods:
- **JSON file** — simple, zero dependencies, good for under ~20 tasks
- **SQLite** — queryable, handles concurrency, tracks history

See the full **[Session Continuity Guide](../docs/session-continuity.md)**
for setup instructions, code examples for both methods, and stop hook
integration for automatic session handoff.

---

## Checkpoint

- [ ] Tier 2 triggers fire when keywords appear in commands
- [ ] Cross-check runs after tier1 completes (check sentinel for `cross_check_done: true`)
- [ ] Save reminder appears after 15 edits
- [ ] Stop hook blocks exit when repos are dirty
- [ ] Backlog loads in tier1 at session start (JSON or SQLite method)

---

**Next:** [Module 6 — Anti-Hallucination Rules](module-6-anti-hallucination.md)
