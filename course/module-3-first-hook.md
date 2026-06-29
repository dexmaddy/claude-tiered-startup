---
layout: default
title: "Module 3: Your First Startup Hook"
parent: Course
nav_order: 3
---

# Module 3: Your First Startup Hook

**Time:** 20 minutes
**Goal:** Build a working Level 1 system — SessionStart hook that generates
a manifest and tier1 files from a YAML config.

---

## What You'll Build

By the end of this module, your Claude Code sessions will:
1. Run infrastructure checks at startup
2. Generate tier1 rule files in a temp directory
3. Print a manifest telling Claude exactly what to read
4. Show a health report with PASS/FAIL for each check

No gates yet — that's Module 4. This module gets the foundation working.

---

## Step 1: Create Your Config (5 minutes)

Create `startup-config.yaml` in your project root:

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md
      description: "Project rules and conventions"
    - name: infra-report
      type: checks
      description: "Infrastructure health"

checks:
  - name: git-clean
    command: "git status --porcelain"
    validator: empty_output
    fail_message: "Uncommitted changes detected"

gates:
  block_until_tier1: false    # We'll enable this in Module 4

stop:
  require_clean_repos: false
```

## Step 2: Create Your First Rules File (5 minutes)

Create `rules/core-rules.md` with your top 5 project rules.
(See the [Bootstrapping Guide](../docs/bootstrapping-guide.md) for templates.)

Minimum viable example:

```markdown
# Core Rules

### project-language
This project uses TypeScript 5.x with strict mode. Do not write JavaScript.

### test-framework
Tests use Vitest, not Jest. Run with: pnpm test

### main-branch
The default branch is "main". Never push directly — always use PRs.
```

## Step 3: Install the Hook (5 minutes)

```bash
# Create the hooks directory
mkdir -p .claude/hooks

# Copy the hook scripts
cp path/to/claude-tiered-startup/hooks/on_session_start.py .claude/hooks/
cp path/to/claude-tiered-startup/hooks/validators.py .claude/hooks/

# Install PyYAML
pip install pyyaml
```

Add to `.claude/settings.json` (create if it doesn't exist):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/on_session_start.py",
            "timeout": 60000
          }
        ]
      }
    ]
  }
}
```

## Step 4: Add to CLAUDE.md (2 minutes)

Add this to your project's CLAUDE.md:

```markdown
## Startup

At session start, the SessionStart hook generates a manifest and tier1 files.
Read the manifest path from the hook output, then read ALL tier1 files listed
before responding to any user message.
```

## Step 5: Test It (3 minutes)

Start a new Claude Code session. You should see output like:

```
STARTUP: 1 OK, 0 FAIL
Manifest: /tmp/manifest-abc123.json
Tier 1: 2 files (28 lines)
ACTION REQUIRED: Read manifest, then read all Tier 1 files.
  - /tmp/tier1-core-rules-abc123.md (25 lines, core-rules)
  - /tmp/tier1-infra-report-abc123.md (3 lines, infra-report)
```

**Verify:** Ask Claude "what are the project rules?" — it should
reference the rules from your core-rules.md file.

---

## Troubleshooting

### "startup-config.yaml not found"
The hook walks up from the current directory looking for the config.
Make sure it's in your project root (where you run Claude Code from).

### "PyYAML not installed"
Run `pip install pyyaml` in the same Python environment that Claude Code uses.
Check with: `python3 -c "import yaml; print('ok')"`

### "FAIL" on a check
The check command failed its validator. Check the detail message.
For `git-clean` failures, commit your outstanding changes first.

### Hook doesn't run
- Verify `.claude/settings.json` is valid JSON (use `python3 -m json.tool`)
- Check that the command path is correct: `python3 .claude/hooks/on_session_start.py`
- Restart Claude Code after changing settings (hooks are loaded at launch)

---

## What You've Built

```
Your project/
├── .claude/
│   ├── settings.json              ← Hook configuration
│   └── hooks/
│       ├── on_session_start.py    ← SessionStart hook
│       └── validators.py          ← Output-based validators
├── startup-config.yaml            ← Your tier/check definitions
├── rules/
│   └── core-rules.md              ← Your project rules
└── CLAUDE.md                      ← Updated with startup instructions
```

At every session start:
1. Hook reads your config
2. Runs infrastructure checks
3. Copies rule files to temp (session-scoped)
4. Writes manifest telling Claude what to read
5. Claude reads the files and has your rules in context

**Limitation:** Claude can still ignore the manifest and start working
without reading the files. Module 4 fixes this with structural gates.

---

## Checkpoint

Before moving on, verify:
- [ ] Starting a new session shows the STARTUP output
- [ ] The manifest lists your tier1 files with correct line counts
- [ ] Your infrastructure checks show OK or expected FAILs
- [ ] Claude can answer questions about your project rules

---

**Next:** [Module 4 — Adding Gates](module-4-gates.md)
