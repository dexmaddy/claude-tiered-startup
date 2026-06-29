# Self-Healing Loop: Bidirectional Rule-Audit Feedback

A pattern where rules feed audit checks AND audit checks feed rules,
creating a system that grows organically from real usage.

---

## The Problem

Most rule systems are write-once:

1. Someone writes rules
2. Someone writes audit checks
3. Over time, new rules appear that no audit check covers
4. Over time, audit checks find issues that no rule addresses
5. The gap between "rules we have" and "rules we need" grows silently

## The Pattern

The self-healing loop connects three components. Drift detection is
structurally enforced via `cross_check.py`: when persistent drift is
found, the script generates `write_back_suggestions` that propose
concrete fixes (manifest updates, config corrections, or items flagged
for investigation). This moves the pattern beyond detection-only — the
system now suggests how to resolve the drift.

```mermaid
graph TD
    A["Rules Files<br/>(what to do)"] -->|"UPDATE RULE fires"| B["Audit Checks<br/>(what to verify)"]
    B -->|"Audit finds scattered items"| A
    C["Session Learnings<br/>(what went wrong)"] -->|"Route to rules"| A
    A -->|"New rule implies check?"| B
    B -->|"Check reveals gap?"| A
    B -->|"Persistent drift detected"| W["cross_check.py generates<br/>write_back_suggestions"]
    W -->|"Suggest manifest update<br/>or investigation"| A

    style A fill:#4a90d9,color:#fff
    style B fill:#5cb85c,color:#fff
    style C fill:#f0ad4e,color:#fff
    style W fill:#9b59b6,color:#fff
```

### Forward Flow: Rule → Audit Check

Every time a rule is added or updated, ask:

> "Does this new rule imply something that should be verified automatically?"

If yes, add a check to your infrastructure checks or cross-check config.

**Examples:**

| New Rule | Implied Check |
|----------|--------------|
| "Use pnpm, not npm" | `grep -r "npm run" scripts/ \| grep -v pnpm \| wc -l` should be 0 |
| "All API endpoints require auth" | `grep -r "@public" routes/ \| wc -l` should be 0 |
| "Database migrations must be reversible" | Each migration file has both `up()` and `down()` |
| "No TODO comments in main branch" | `git diff main \| grep TODO \| wc -l` should be 0 |

### Backward Flow: Audit → Rule

When an audit check discovers something unexpected, ask:

> "Does this finding represent a pattern that should be a rule?"

If yes, add a rule to your rules file, then apply the forward flow
(does this new rule need a check?).

**Examples:**

| Audit Finding | New Rule |
|--------------|----------|
| "3 files still reference old API v2 path" | "After any path change, grep the full codebase for the old path" |
| "Config file has stale count (says 12, actually 15)" | "After adding items, update all references to the count" |
| "Two scripts import from deprecated module" | "Module X is deprecated, import from module Y instead" |

### The Learning Input

Session learnings (mistakes, surprises, operational discoveries) are the
third input. They get routed to rules, which trigger the forward flow:

```mermaid
graph LR
    A["Failure happens"] --> B["Learning captured"]
    B --> C["Routed to rules file"]
    C --> D{"Does rule imply<br/>a check?"}
    D -->|YES| E["Add check"]
    D -->|NO| F["Done"]

    style A fill:#d9534f,color:#fff
    style E fill:#5cb85c,color:#fff
```

## Implementation

### With YAML Config (Method A)

After editing `rules/core-rules.md`, check your `startup-config.yaml`:

```yaml
# Ask: does the new rule imply a verifiable check?
checks:
  - name: no-npm-usage           # Added because of "use pnpm" rule
    command: "grep -r 'npm run' scripts/ | grep -v pnpm | wc -l | tr -d ' '"
    validator: "equals:0"
    fail_message: "npm usage found — should be pnpm"
```

### With SQLite (Method B)

```sql
-- After adding a rule
INSERT INTO rules (name, content, category, tier)
VALUES ('use-pnpm', 'Use pnpm, not npm...', 'tooling', 1);

-- Ask: does this imply a check?
INSERT INTO checks (name, command, validator, fail_message)
VALUES ('no-npm-usage',
        'grep -r "npm run" scripts/ | grep -v pnpm | wc -l | tr -d '' ''',
        'equals:0',
        'npm usage found — should be pnpm');
```

### Infinite Loop Guard

Both directions MUST check "is this already there?" before adding:

- Before adding a rule: search existing rules for a similar entry
- Before adding a check: search existing checks for one that covers the same thing
- Never re-process items you just added in the same session

The rule is: act on NEW items only. If it's already captured, move on.

## When to Apply

Apply the self-healing check:

- After adding any rule → "Does this imply a check?"
- After any audit finding → "Does this imply a rule?"
- After any session learning → "Which rule file does this belong to?"
- After any file edit → "Is this scattered information that belongs in a consolidated file?"

The last question is RULE ZERO — see the [Rule Zero](rule-zero.md) pattern.

### Standalone Audit Runner

The `audit.py` script provides on-demand execution of the check side of
the self-healing loop. While startup checks run automatically at session
start, the audit runner lets you verify infrastructure state at any point
during a session. It uses the same validator framework, so checks written
for startup work identically when run standalone. See the
[Audit Runner](audit-runner.md) reference for usage and configuration.
