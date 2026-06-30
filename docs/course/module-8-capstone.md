# Module 8: Capstone — Wire It All Together

**Time:** 30 minutes
**Goal:** Build a complete, working AI Agent Harness for YOUR project
using everything from Modules 1-7.

---
!!! tip "Using SQLite instead of YAML?"
    This module shows YAML examples. If you chose SQLite in the setup wizard,
    see the [Data Store Mapping Guide](../reference/data-store-mapping.md) for
    equivalent database commands.

---

## Step-by-Step Build

### Phase 1: Content (10 minutes)

**1.1 — Write your tier1 rules**

Create `rules/core-rules.md` with 5-10 rules covering:
- [ ] Project language and version
- [ ] Package manager and key commands
- [ ] Branch naming and PR conventions
- [ ] Key architectural decisions ("we use X, not Y")
- [ ] Active project state (what's being worked on now)

**1.2 — Write your tier2 rules**

Create specialized rule files for task-specific knowledge:
- [ ] `rules/deploy-rules.md` — deployment procedures
- [ ] `rules/testing-rules.md` — test conventions
- [ ] `rules/api-rules.md` — API standards

Only create files for areas where the agent has made mistakes.

**1.3 — Add anti-hallucination rules**

Copy `rules/anti-hallucination-rules.md` from the starter kit.
Decide: tier1 (if you summarize often) or tier2 (with triggers
like "summarize", "extract", "report").

### Phase 2: Configuration (5 minutes)

**2.1 — Create `startup-config.yaml`**

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md
      description: "Project conventions and active state"
    - name: ah-rules
      source: rules/anti-hallucination-rules.md
      description: "Anti-hallucination framework"
    - name: infra-report
      type: checks
      description: "Infrastructure health"

  tier2:
    - name: deploy-rules
      triggers: ["deploy", "release", "production", "staging", "CI"]
      source: rules/deploy-rules.md
    - name: testing-rules
      triggers: ["test", "spec", "coverage", "mock"]
      source: rules/testing-rules.md

checks:
  - name: git-clean
    command: "git status --porcelain"
    validator: empty_output
  - name: build-passes
    command: "npm run build --silent 2>&1 | tail -1"
    validator: "contains:success"
    optional: true
  - name: deps-installed
    command: "test -d node_modules && echo ok || echo missing"
    validator: "contains:ok"

gates:
  block_until_tier1: true
  tier2_keyword_scan: true
  keyword_scan_fields: [command, file_path, prompt, description]
  keyword_scan_max_chars: 120
  prompt_health_warnings: [40, 60, 80]

cross_check:
  expected_counts:
    rule_files:
      command: "find rules/ -name '*.md' | wc -l | tr -d ' '"
      expected: 3     # adjust to your actual count
      auto_heal: false

stop:
  require_clean_repos: true
  require_transcript: false
  max_retries: 8
```

### Phase 3: Installation (5 minutes)

**Option A — Use the setup wizard (recommended):**

```bash
python3 path/to/ai-agent-harness/setup.py
```

The wizard handles everything: detects your agent platform, asks your
preferred data store (YAML, SQLite, or PostgreSQL), copies the right hook
scripts, generates config, creates sample rules, wires settings, and
installs dependencies. Choose **Level 4** for the full architecture.

For CI/automation, use non-interactive mode:
```bash
python3 setup.py --non-interactive --platform claude --store sqlite --level 4
```

**Option B — Manual install:**

```bash
mkdir -p .agent/hooks
cp path/to/ai-agent-harness/hooks/*.py .agent/hooks/
pip install pyyaml
```

Then copy `examples/level-4-full/settings.json` to your agent's settings
file and update your agent instructions:

```markdown
## Startup

This project uses the AI Agent Harness.
At session start, the SessionStart hook generates a manifest and tier1 files.
Read the manifest from hook output, then read ALL tier1 files before doing
any work. Gates enforce this — tools are blocked until all files are read.

Do NOT skip startup. Do NOT explain what startup does — just do it.
```

### Phase 4: Test (5 minutes)

**4.1 — Run the smoke test**

```bash
python3 path/to/ai-agent-harness/tests/smoke_test.py --verbose
```

All checks should pass.

**4.2 — Live test**

Start a AI agent session:
1. Verify startup output shows your tier1 files
2. Try using a tool before reading tier1 → should be blocked
3. Read all tier1 files → tools should unblock
4. Run a command with a tier2 trigger word → should prompt to read tier2
5. End session with uncommitted changes → stop hook should block

### Phase 5: First Feedback Loop (5 minutes)

**5.1 — Intentionally trigger a failure**

Ask the agent something where it might make a mistake (use the wrong
API version, wrong test framework, wrong file path).

**5.2 — Capture the failure**

```markdown
**What happened:** _______________
**Root cause:** _______________
```

**5.3 — Write the rule and add to core-rules.md**

**5.4 — Add a check if possible**

**5.5 — Commit everything**

```bash
git add rules/ startup-config.yaml .agent/
git commit -m "Add AI Agent Harness with core rules and infrastructure checks"
```

---

## Complete Architecture: All 5 Hooks

This is the full execution flow of the Level 4 architecture. Every hook
point and its responsibilities are shown here for reference (see also
[Module 5](module-5-advanced.md) for detailed explanations of each stage).

```
Session start → SessionStart hook (on_session_start.py)
  → Checks infrastructure (validators parse stdout, not exit codes)
  → Generates tier1 + tier2 files from config
  → Writes manifest.json + sentinel.json
       │
Every user message → UserPromptSubmit hook (on_prompt_submit.py)
  → Detects /clear (context reset) — re-runs startup if triggered
  → Blocks until tier1 complete
  → Surfaces infra FAILs on first prompt
  → Warns at prompt thresholds (40, 60, 80)
       │
Every tool call → PreToolUse hook (gate_check.py)
  → Always allows Read (tracks file reads in sentinel)
  → Auto-allows git commit/push (version control never blocked)
  → Blocks non-Read tools until tier1 complete
  → Runs cross_check.py once after tier1 completes
  → Triggers tier2 loading on keyword matches
  → DB mode: stale fact gate (Gate 4)
       │
Every Write/Edit → PostToolUse hook (on_edit.py)
  → Save reminders
  → Rule Zero enforcement (scattered content detection)
  → File sync (if configured)
       │
Session end → Stop hook (on_stop.py)
  → Blocks until repos clean
  → Runs audit checks (if require_audit_pass)
  → Self-verification enforcement
  → DB mode: session summary + no-truncation checks
  → Retries up to N times, then allows exit
```

---

## Verification Checklist

Run through each item and confirm:

### Startup
- [ ] SessionStart hook runs and shows STARTUP output
- [ ] Manifest lists correct number of tier1 and tier2 files
- [ ] Infrastructure checks show expected results
- [ ] Tier1 files are generated in temp directory

### Gates
- [ ] Non-Read tools blocked before tier1 is read
- [ ] All tools allowed after tier1 is complete
- [ ] Prompt gate injects "read first" message when incomplete
- [ ] Health warnings appear at configured prompt thresholds

### Tier 2
- [ ] Keyword triggers fire correctly
- [ ] No false positives on common words
- [ ] Once a tier2 file is read, its trigger doesn't fire again

### Cross-Check
- [ ] Runs once after tier1 completes
- [ ] Reports drift if expected counts don't match
- [ ] Sentinel shows `cross_check_done: true`

### Stop
- [ ] Blocks exit when repos are dirty (if configured)
- [ ] Allows exit after cleanup
- [ ] Doesn't trap user indefinitely (max retries)

### Content
- [ ] Core rules cover your top 5-10 project conventions
- [ ] Anti-hallucination rules are in tier1 or tier2
- [ ] At least one rule was born from a real failure

### PostToolUse (Level 4)
- [ ] `on_edit.py` wired in settings.json for PostToolUse events
- [ ] Save reminders fire after Write/Edit operations
- [ ] Rule Zero scattered-content detection active (if configured)
- [ ] File sync working (if configured)

### Consistency Checker (Level 4)
- [ ] `cross_check.py` runs once after tier1 completes
- [ ] Auto-heals safe discrepancies (e.g., stale counts)
- [ ] Generates `write_back_suggestions` for persistent drift
- [ ] Sentinel shows `cross_check_done: true` after run

### Self-Verification ([enforced via on_stop hook](../reference/self-verification.md))
- [ ] Re-run startup — does the output match your expectations?
- [ ] All files committed and pushed?
- [ ] No stale references (grep for old paths/counts)?
- [ ] A second run produces the same result?
- [ ] Stop hook blocks exit if infra files edited after last check

### Rule Zero ([enforced via on_edit hook](../reference/rule-zero.md))
- [ ] Agent instructions include the Rule Zero prompt
- [ ] on_edit hook scans for scattered content across consolidated files
- [ ] At least one rule triggered a corresponding audit check

### Audit Runner ([on-demand checks](../reference/audit-runner.md))
- [ ] `checks/audit-checks.yaml` customized for your project
- [ ] `python3 hooks/audit.py --verbose` runs clean
- [ ] Stop hook has `require_audit_pass: true` (optional but recommended)

### Stop Hook Extras
- [ ] `shutdown_steps` configured for project-specific exit checks (linting, formatting, etc.)
- [ ] DB mode: `require_session_summary: true` ensures learnings are captured each session
- [ ] DB mode: edit logging active (`AGENT_DB_PATH` set, `rule_log` table populated)
- [ ] DB mode: no-truncation enforcement active (stop hook verifies stored rule length matches source)

---

## What's Next

Your system is now live. Here's how to maintain it:

### Weekly (2 minutes)
- Review any new failures from the past week
- Write rules for failures that aren't covered
- Update the `expected` counts in cross_check if they've changed

### Monthly (10 minutes)
- Audit tier1 size — is it under 1500 lines?
- Promote high-frequency tier2 rules to tier1
- Retire rules that haven't triggered in 20+ sessions
- Update infrastructure checks for project changes

### Per Failure
- Capture immediately
- Write the rule
- Ask: can I verify this with a check?
- If 3+ violations despite rule being loaded → escalate to hook

---

## Congratulations

You've built a self-improving agent session management system with 5 hooks
(SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop) that:

1. **Loads the right context** — tier1 always, tier2 on demand
2. **Enforces loading** — gates prevent work before rules are read
3. **Guards output quality** — PostToolUse enforces Rule Zero on every write
4. **Detects drift** — cross-check catches stale references
5. **Prevents hallucination** — 14 research-backed rules
6. **Improves itself** — failures become rules, rules become checks

The system started with 5 rules. It will grow organically as you use it.
Every failure makes it stronger. Every rule makes the next session more
reliable.

---

**Course complete.** Return to the [Course Index](index.md) for reference.
