# Tiered Startup Architecture for Claude Code

A progressive, hook-based system that ensures Claude Code sessions start with
the right context loaded, enforced structurally — not by hoping Claude reads
your CLAUDE.md carefully.

## The Problem

Without managed startup, Claude Code sessions suffer from three issues:

1. **Context waste** — loading everything every session burns tokens on rules
   that aren't needed for the current task. A 3000-line rule set costs ~4K
   tokens on every session, even when you're just fixing a typo.

2. **Rule drift** — facts, counts, and references go stale. Your CLAUDE.md
   says "58 rules" but the DB has 62. No one notices until a rule is missed.

3. **Startup chaos** — CLAUDE.md says "read these files" but there's no
   enforcement. Claude skips files, partially loads context, or starts working
   before critical rules are loaded. Writing "you must read X" in a markdown
   file is documentation, not enforcement.

This architecture solves all three with **tiered loading** (load what's needed),
**structural gates** (block tools until context is loaded), and **drift detection**
(catch stale references automatically).

## Architecture Overview

Four Claude Code hook points work together:

```
SessionStart                    PreToolUse
    |                               |
    v                               v
[Read config]                 [Is tool = Read?]
[Run checks]                    yes: track file read, allow
[Generate tier1 files]          no:  is tier1 complete?
[Write manifest.json]                yes: check tier2 triggers, allow
[Write sentinel.json]                no:  BLOCK with reason
    |                               |
    v                               v
UserPromptSubmit                Stop
    |                               |
    v                               v
[Is tier1 complete?]          [Are repos clean?]
  no:  inject "read first"    [Is transcript saved?]
  yes: track prompt count       no:  exit 2 (retry)
       warn at thresholds       yes: exit 0 (allow)
```

**Manifest** (`manifest.json`) — lists all tier1/tier2 files with paths, sizes,
and trigger keywords. Generated fresh each session.

**Sentinel** (`startup-complete-{session}.json`) — tracks which files Claude has
read, whether tier1 is complete, and whether cross-check has run. Session-scoped
to prevent collisions between concurrent or resumed sessions.

## Quick Start (Level 1)

The simplest useful version — manifest + tier1 loading, no gates.

### 1. Install

```bash
# Copy hooks to your project
mkdir -p .claude/hooks
cp hooks/on_session_start.py .claude/hooks/
cp hooks/validators.py .claude/hooks/

# Install dependency
pip install pyyaml
```

### 2. Create your config

Copy `config.example.yaml` to your project root as `startup-config.yaml`:

```yaml
tiers:
  tier1:
    - name: project-rules
      source: docs/rules.md
      description: "Core project rules and conventions"
    - name: infra-report
      type: checks
      description: "Infrastructure health"

checks:
  - name: git-clean
    command: "git status --porcelain"
    validator: empty_output
  - name: tests-pass
    command: "npm test --silent 2>&1 | tail -1"
    validator: "contains:passing"
    optional: true

gates:
  block_until_tier1: false    # Level 1: no blocking
```

### 3. Add the hook

Add to your `.claude/settings.json` (or copy from `examples/level-1-minimal/`):

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 .claude/hooks/on_session_start.py",
        "timeout": 60000
      }]
    }]
  }
}
```

### 4. Start a session

Claude sees this output at session start:

```
STARTUP: 2 OK, 0 FAIL
Manifest: /tmp/manifest-abc123.json
Tier 1: 2 files (45 lines)
ACTION REQUIRED: Read manifest, then read all Tier 1 files.
  - /tmp/tier1-project-rules-abc123.md (30 lines, project-rules)
  - /tmp/tier1-infra-report-abc123.md (15 lines, infra-report)
```

Add to your CLAUDE.md:

```markdown
## Startup
Read the manifest from SessionStart hook output, then read all Tier 1 files
before responding to any user message.
```

---

## Level 2: Add Gates

Level 1 relies on Claude voluntarily reading files. Level 2 **enforces** it —
Claude cannot use any tool except Read until all tier1 files are loaded.

### What changes

1. **PreToolUse gate** — blocks Bash, Write, Edit, Agent, etc. until tier1 is
   complete. Only Read is allowed (so Claude can load the files).
2. **UserPromptSubmit gate** — injects "read files first" into Claude's context
   if tier1 is incomplete. Also tracks prompt count and warns at thresholds.

### Install

```bash
cp hooks/gate_check.py .claude/hooks/
cp hooks/on_prompt_submit.py .claude/hooks/
```

Update `startup-config.yaml`:

```yaml
gates:
  block_until_tier1: true      # NOW ENFORCED
  prompt_health_warnings: [40, 60, 80]
```

Copy settings from `examples/level-2-gated/settings.json` or add the
PreToolUse and UserPromptSubmit hooks to your existing settings.

### How it works

1. SessionStart generates tier1 files + writes sentinel with `stage: "tier1_pending"`
2. Claude tries to use Bash → PreToolUse gate reads sentinel → tier1 incomplete → **DENIED**
3. Claude reads tier1 files → gate_check tracks each Read in sentinel
4. All tier1 files read → sentinel updated to `stage: "complete"`
5. Claude tries Bash again → gate checks sentinel → tier1 complete → **ALLOWED**

The UserPromptSubmit hook adds a second layer: if Claude somehow ignores the
PreToolUse denial, the prompt gate injects a message saying "read files first"
that Claude sees before composing its response.

---

## Level 3: On-Demand Tier 2

Not all rules are needed every session. Tier 2 files load **only when relevant
keywords appear** in Claude's tool calls.

### What changes

Add tier2 definitions with trigger keywords to your config:

```yaml
tiers:
  tier2:
    - name: api-rules
      triggers: ["api", "endpoint", "REST", "swagger"]
      source: docs/api-rules.md

    - name: deploy-guide
      triggers: ["deploy", "CI", "pipeline", "release"]
      source: docs/deploy-guide.md
```

### How it works

1. Claude runs `Bash("curl api.example.com/...")` 
2. PreToolUse gate scans the command text for tier2 triggers
3. Finds "api" matches the `api-rules` trigger → **DENIES** with message:
   "Tier 2 files triggered — read before proceeding: api-rules"
4. Claude reads the file → gate tracks it → next tool call is allowed

**Keyword scanning is limited** to prevent false positives:
- Only scans specific JSON fields (command, file_path, prompt, description)
- Only scans the first N characters of each field (default: 120)
- Case-insensitive matching

### Cross-Check Drift Detection

After tier1 loads, run a single drift check comparing expected vs actual state.
This catches stale references before they cause problems.

Add a script that checks your project's invariants:

```python
# Example: verify rule count in docs matches actual count
expected = manifest["expected_counts"]["rules"]
actual = len(list(Path("rules/").glob("*.md")))
if expected != actual:
    print(f"DRIFT: rules count {expected} in manifest vs {actual} on disk")
```

The cross-check runs once per session (tracked by `cross_check_done` in sentinel).

---

## Level 4: Full Architecture

### Stop Hook

Block session exit until cleanup is done:

```bash
cp hooks/on_stop.py .claude/hooks/
```

```yaml
stop:
  require_clean_repos: true
  require_transcript: false
  max_retries: 8
```

The stop hook returns exit code 2 (retry) when checks fail. Claude sees the
failure message and can fix the issue (e.g., commit uncommitted files). After
max retries, it exits cleanly to avoid trapping the user.

### Output-Based Validators

Shell exit codes lie. A piped command like `git status | grep -v node_modules`
returns 0 even when there are uncommitted files (because grep succeeded). The
validator registry parses stdout instead:

| Validator | Passes when |
|-----------|-------------|
| `empty_output` | stdout is empty (whitespace-only) |
| `not_empty` | stdout has content |
| `contains:text` | stdout contains text (case-insensitive) |
| `equals:text` | stdout exactly equals text (stripped) |
| `regex:pattern` | regex matches anywhere in stdout |

Add custom validators by extending `validators.py`:

```python
VALIDATORS["my_check"] = lambda stdout: (
    int(stdout.strip()) > 0,
    stdout.strip()
)
```

### Session-Scoped Isolation

All temp files include the session ID suffix (`-{SESSION_ID}`). This prevents:
- Concurrent sessions overwriting each other's state
- Resumed sessions reading stale sentinel from a previous run
- Race conditions between multiple Claude Code instances

---

## Customization Checklist

When adapting this to your project:

- [ ] **Tier 1 files** — what rules/context must Claude always have? Keep under ~1500 lines total
- [ ] **Tier 2 files** — what's only needed sometimes? Pick trigger keywords that are specific enough to avoid false positives
- [ ] **Infrastructure checks** — what should be verified at startup? (DB health, git clean, tests pass, services running)
- [ ] **Validators** — do any checks need custom stdout parsing?
- [ ] **Prompt thresholds** — at what prompt counts should Claude warn about context health?
- [ ] **Stop checks** — what must be done before session exit? (commit, save transcript, sync files)
- [ ] **File paths** — update `startup-config.yaml` sources to point to your actual files

---

## Lessons Learned

These insights emerged from building and iterating on this system across dozens
of sessions:

1. **Documenting is not doing.** Writing "Claude must read X at startup" in
   CLAUDE.md doesn't make it happen. Structural enforcement (hooks that block
   tools) is the only reliable mechanism. If it's not enforced, it's optional.

2. **Exit codes lie.** Shell commands with pipes, `||`, subshells, and error
   handling masks return 0 when they shouldn't. Parse stdout with validators
   instead of trusting `$?`.

3. **Session-scope everything.** Temp files without session IDs cause mysterious
   failures when sessions resume or run concurrently. Always suffix with session ID.

4. **Tier wisely.** The split between tier1 and tier2 should be based on
   *frequency of need*, not *importance*. Critical API rules that only matter
   when doing API work belong in tier2 with an "api" trigger — not in tier1
   where they waste tokens on every session.

5. **Bound your loops.** Cross-check drift detection must be bounded (2 passes
   max, then continue). Unbounded self-healing loops can spiral when fixes
   create new drift. Fix what's safe, log the rest, move on.

6. **Gate, don't nag.** A CLAUDE.md instruction that says "please read X first"
   is a suggestion. A PreToolUse hook that returns `permissionDecision: "deny"`
   is a gate. Gates work. Suggestions don't.

7. **Track reads, not intentions.** The sentinel tracks which files Claude
   *actually read* (via Read tool path matching), not which files it was
   *told to read*. This closes the gap between "I loaded the rules" and
   "the rules are in my context."

8. **More reasoning = worse faithfulness.** Giving the LLM more thinking
   time makes summaries *less* faithful to sources (r = -0.685). Use
   reasoning for verification, never for generation. See `rules/anti-hallucination-rules.md`.

---

## Anti-Hallucination Rules

The `rules/` directory includes a research-backed framework of 14 cognitive
rules for reducing hallucination in LLM-generated summaries. These are
generic — they apply to any summarization task, not just one domain.

The rules are organized into 5 phases (READ → WRITE → VERIFY PASS 1 →
VERIFY PASS 2 → SIGN-OFF) because LLMs skip rules in the middle of flat
lists (U-shaped attention bias). Each rule cites peer-reviewed research.

To use them, include `rules/anti-hallucination-rules.md` as a Tier 1 file
in your config:

```yaml
tiers:
  tier1:
    - name: ah-rules
      source: rules/anti-hallucination-rules.md
      description: "Anti-hallucination rules for faithful summaries"
```

Or reference them directly in your LLM prompts when generating summaries.

---

## Getting Started

**New to this?** Take the **[Mini Course](course/README.md)** — 8 modules, ~2.5 hours,
builds a complete working system for your project step by step.

**Want to jump in?** Use these references:

1. **[Bootstrapping Guide](docs/bootstrapping-guide.md)** — create your first 5 rules
   in 15 minutes, with starter kits for web apps, data pipelines, and infrastructure
2. **[Rule Evolution Template](docs/rule-evolution-template.md)** — the pattern for
   turning failures into structural enforcement: failure → learning → rule → audit → hook
3. **[Smoke Test](tests/smoke_test.py)** — verify your setup works end-to-end:
   `python3 tests/smoke_test.py --verbose`

---

## File Structure

```
claude-tiered-startup/
├── README.md                          # This guide
├── config.example.yaml                # Template config — copy and customize
├── settings.example.json              # Full hook configuration
├── hooks/
│   ├── on_session_start.py            # SessionStart: config → manifest + tier files
│   ├── gate_check.py                  # PreToolUse: enforce tier loading
│   ├── on_prompt_submit.py            # UserPromptSubmit: startup gate + health warnings
│   ├── on_stop.py                     # Stop: shutdown checks with retry
│   ├── on_edit.py                     # PostToolUse: post-write actions (sync, reminders)
│   ├── cross_check.py                 # Drift detection: expected vs actual state
│   └── validators.py                  # Output-based check validators
├── rules/
│   └── anti-hallucination-rules.md    # 14 research-backed anti-hallucination rules
├── docs/
│   ├── bootstrapping-guide.md         # Create your first 5 rules in 15 min
│   └── rule-evolution-template.md     # Failure → learning → rule → hook pattern
├── course/                            # 8-module mini course (~2.5 hours)
│   ├── README.md                      # Course index and self-assessment
│   ├── module-1-the-problem.md        # Why unmanaged sessions fail
│   ├── module-2-architecture.md       # The 4-hook system explained
│   ├── module-3-first-hook.md         # Hands-on: build Level 1
│   ├── module-4-gates.md              # Hands-on: add structural enforcement
│   ├── module-5-advanced.md           # Tier 2, drift detection, stop hook
│   ├── module-6-anti-hallucination.md # 14 research-backed rules
│   ├── module-7-feedback-loop.md      # Failure → rule → enforcement pipeline
│   └── module-8-capstone.md           # Wire it all together for your project
├── tests/
│   └── smoke_test.py                  # Verify full hook chain works (18 checks)
├── examples/
│   ├── level-1-minimal/settings.json  # Just SessionStart
│   ├── level-2-gated/settings.json    # + PreToolUse + UserPromptSubmit
│   └── level-4-full/settings.json     # All 4 hooks
└── LICENSE                            # MIT
```

## Requirements

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- Claude Code with hooks support

## License

MIT — use it, adapt it, share it.
