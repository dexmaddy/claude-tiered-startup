# Rule Evolution: From Failure to Enforcement

Rules that exist "just in case" get ignored. Rules born from real failures
get followed. This document shows the pattern for evolving incidents into
structural enforcement.

---

## The Evolution Chain

```
FAILURE                    Something went wrong
   ↓
LEARNING                   Why it went wrong (root cause, not symptom)
   ↓
RULE                       What to do differently (in rules/*.md)
   ↓
AUDIT CHECK                How to verify the rule is followed (in config checks)
   ↓
HOOK ENFORCEMENT           Structural gate that prevents the failure (in hooks/)
```

Each step is optional — not every failure needs a hook. But every failure
needs at least a learning, and most need a rule.

---

## Step-by-Step Template

### 1. Capture the Failure

When something goes wrong, record it immediately:

```markdown
**Date:** YYYY-MM-DD
**What happened:** [Factual description — what was the output?]
**What was expected:** [What should have happened instead?]
**Impact:** [Was work lost? Was wrong output sent? How long to fix?]
```

**Example:**
```markdown
**Date:** 2026-06-15
**What happened:** Generated summary referenced config file at /etc/app/config.yaml
but the actual path is /opt/app/config.yaml. User deployed with wrong path.
**What was expected:** Summary should use the actual path from the project.
**Impact:** 20 minutes debugging a "file not found" error in staging.
```

### 2. Identify the Root Cause

Ask "why" until you hit the structural cause:

```
Why was the path wrong?
  → the agent used a common default path instead of the project's actual path.
Why did the agent use a default?
  → The actual path wasn't in any loaded context.
Why wasn't it in context?
  → No rule file lists project-specific paths.
ROOT CAUSE: Project-specific facts not captured in tier1 rules.
```

### 3. Write the Rule

```markdown
### config-file-paths

All configuration files live under /opt/app/, NOT /etc/app/.
The /etc/app/ path is a common convention but this project uses /opt/app/.

- DO: reference /opt/app/config.yaml
- DON'T: reference /etc/app/config.yaml (does not exist)

**Why:** the agent used the conventional /etc/ path in a generated summary,
causing a deployment failure. The project has always used /opt/app/.

**How to apply:** When referencing any config file, verify the path
exists in the project before using it.
```

### 4. Add an Audit Check (optional)

If the rule is about verifiable state, add a check to `startup-config.yaml`:

```yaml
checks:
  - name: config-paths-valid
    command: "test -f /opt/app/config.yaml && echo exists"
    validator: "contains:exists"
    fail_message: "Config file missing at expected path"
```

### 5. Upgrade to Hook Enforcement (optional, for critical rules)

For rules that MUST NOT be violated, add enforcement at the hook level.

**Example: prevent writing wrong paths**

Add to `gate_check.py` (as a custom gate):

```python
# Gate N: Block writes that reference incorrect paths
FORBIDDEN_PATHS = ["/etc/app/"]  # known-wrong paths for this project
if tool_name in ("Write", "Edit"):
    content = tool_input.get("new_string", "") + tool_input.get("content", "")
    for bad_path in FORBIDDEN_PATHS:
        if bad_path in content:
            deny(f"Blocked: {bad_path} is incorrect. Use /opt/app/ instead.")
            return
```

---

## Evolution Examples

### Example A: Missing Context → Tier 1 Rule

```
Failure:  the agent used Python 3.9 syntax but project requires 3.12+
Learning: Project Python version not in any loaded file
Rule:     "This project uses Python 3.12+. Use match/case, f-strings,
           type unions (X | Y), and other 3.12 features freely."
Check:    command: "python3 --version"
          validator: "contains:3.12"
Hook:     None needed — rule is sufficient
```

### Example B: Repeated Mistake → Tier 2 with Trigger

```
Failure:  The agent ran "npm test" but project uses "pnpm test"
Learning: Package manager confusion only happens during test/build tasks
Rule:     "This project uses pnpm, not npm. All commands: pnpm install,
           pnpm test, pnpm build, pnpm dev."
Check:    command: "which pnpm"
          validator: not_empty
Hook:     Tier 2 trigger: ["test", "build", "install", "dev", "pnpm", "npm"]
          → loads rules/package-manager.md with the correct commands
```

### Example C: Critical Mistake → Full Hook Enforcement

```
Failure:  The agent ran "git push --force" on main branch
Learning: Force-push to main should never happen from automation
Rule:     "Never force-push to main or production branches."
Check:    command: "git branch --show-current"
          validator: not_empty
Hook:     PreToolUse gate in gate_check.py:
          if "push" in command and ("--force" in command or "-f" in command):
              if any(b in command for b in ["main", "master", "production"]):
                  deny("BLOCKED: force-push to protected branch")
```

### Example D: Subtle Mistake → Anti-Hallucination Rule

```
Failure:  Summary said "migration completed successfully" but source said
          "migration started" — the agent inferred completion from starting
Learning: LLMs infer outcomes from actions (started → completed)
Rule:     R30 — No interpretive commentary. Report what the source says,
          not what likely happened next.
Check:    None (requires human review)
Hook:     Include anti-hallucination-rules.md in tier1 so R30 is always loaded
```

---

## Rule Hygiene

### When to Merge Rules
If two rules address the same root cause, merge them. Five rules saying
"don't use npm" in different ways is worse than one clear rule.

### When to Promote Rules
- Tier 2 → Tier 1: if the rule triggers in >50% of sessions
- Rule → Hook: if the rule has been violated 3+ times despite being loaded

### When to Retire Rules
- The project changed and the rule no longer applies
- The rule has never triggered (was too specific or hypothetical)
- A hook now prevents the failure structurally (rule becomes redundant)

### The 80/20 Split
Most projects need ~5-10 tier1 rules and ~10-20 tier2 rules. If you have
50+ rules in tier1, you're probably including things that should be tier2
or that the agent already knows from the codebase itself.

**Rules should capture what ISN'T in the code:**
- Project conventions that aren't enforced by linters
- Facts that change over time (URLs, versions, environment details)
- Historical decisions ("we chose X because Y, don't revisit")
- Workflow sequences ("deploy requires A then B then C, not just C")
