# Bootstrapping Guide: Your First 5 Rules

This guide walks you through creating your first tier1 rules file — the
content that makes the hooks actually useful. Takes ~15 minutes.

---

## Step 1: Identify Your Top 5 Repeated Mistakes

Every project has patterns the agent gets wrong repeatedly. Think about the
last 5 times you had to correct the agent. Write them down:

```
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________
4. _______________________________________________
5. _______________________________________________
```

**Common examples by project type:**

| Project Type | Typical Mistakes |
|-------------|-----------------|
| Web app | Wrong API endpoint paths, outdated component names, missing auth headers |
| Data pipeline | Wrong column names, stale table schemas, incorrect join keys |
| ML project | Wrong model names, outdated hyperparameters, incorrect metric thresholds |
| Infrastructure | Wrong service names, stale IP ranges, incorrect config paths |
| Monorepo | Editing wrong package, importing from wrong workspace, stale cross-references |

## Step 2: Convert Mistakes to Rules

For each mistake, write a rule with this template:

```markdown
### rule-name-in-kebab-case

[One sentence stating the rule clearly.]

- DO: [correct behavior with specific example]
- DON'T: [the mistake, with the specific wrong thing]

**Why:** [What went wrong — the actual incident, not a hypothetical.]

**How to apply:** [When to check this rule — what task or context triggers it.]
```

**Example — Web App:**

```markdown
### api-base-url

All API calls use /api/v2/ prefix, not /api/v1/. The v1 endpoints were
removed in the March 2026 migration but still appear in old documentation.

- DO: fetch("/api/v2/users")
- DON'T: fetch("/api/v1/users")

**Why:** the agent used v1 endpoints three times in one session because the
old README still referenced them. Each time the app threw 404s.

**How to apply:** Before writing any fetch/axios call, verify the endpoint
exists in src/routes/api/.
```

**Example — Data Pipeline:**

```markdown
### schema-source-of-truth

The live schema is in migrations/latest.sql, NOT in the README table.
The README table was last updated in January and is missing 4 columns.

- DO: Check migrations/latest.sql for column names and types
- DON'T: Trust the schema table in README.md

**Why:** The agent added a query using column "user_email" from the README
but the actual column is "email" (renamed in migration 042).

**How to apply:** Before writing any SQL query, read the migration files
or run DESCRIBE on the target table.
```

**Example — Infrastructure:**

```markdown
### deploy-target-environments

Production deploys go to us-east-1 (primary) and eu-west-1 (secondary).
Staging is us-west-2 ONLY. There is no staging in eu-west-1.

- DO: Deploy staging to us-west-2
- DON'T: Deploy staging to eu-west-1 (that's production secondary)

**Why:** The agent suggested deploying a staging test to eu-west-1, which
would have hit the production secondary region.

**How to apply:** Before any deploy command, verify the target region
matches the environment.
```

## Step 3: Save as Your First Tier 1 File

Create `rules/core-rules.md`:

```markdown
# Core Project Rules

These rules prevent the most common mistakes in this project.
Every rule exists because the mistake actually happened.

## [Paste your 5 rules here, using the template from Step 2]
```

## Step 4: Wire It Into Your Config

Edit `startup-config.yaml`:

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md
      description: "Core project rules — prevent the top 5 repeated mistakes"
    - name: infra-report
      type: checks
      description: "Infrastructure health"
```

## Step 5: Test It

Start a new AI agent session. You should see:

```
STARTUP: X OK, Y FAIL
Tier 1: 2 files (N lines)
ACTION REQUIRED: Read manifest, then read all Tier 1 files.
```

the agent now loads your rules at the start of every session.

---

## Growing Beyond 5 Rules

After your initial 5 rules, the system grows organically:

1. **the agent makes a mistake** → you correct it
2. **Write the correction as a rule** → add to `rules/core-rules.md`
3. **Ask: should this be tier1 or tier2?**
   - Tier 1 if it applies to most sessions (coding standards, project facts)
   - Tier 2 if it only applies to specific tasks (deploy rules, API rules)
4. **If tier2: pick trigger keywords** → what tool calls signal this task?

**When to split files:**
- Over 50 rules → split by category (coding, deploy, data, testing)
- Over 1500 total tier1 lines → move lower-frequency rules to tier2

**When to add checks:**
- A rule is about verifiable state → add an infra check
  - "DB must have table X" → `sqlite3 db.db ".tables" | grep X`
  - "Config must have key Y" → `grep Y config.yaml`
  - "No TODO comments in main" → `git diff main | grep TODO | wc -l`

---

## Project-Type Starter Kits

### Web Application (React/Next.js)

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md    # API paths, component locations, auth patterns
    - name: infra-report
      type: checks

  tier2:
    - name: deploy-rules
      triggers: ["deploy", "vercel", "CI", "release"]
      source: rules/deploy-rules.md
    - name: testing-rules
      triggers: ["test", "jest", "cypress", "spec"]
      source: rules/testing-rules.md

checks:
  - name: build-passes
    command: "npm run build --silent 2>&1 | tail -1"
    validator: "contains:Compiled successfully"
    optional: true
  - name: no-type-errors
    command: "npx tsc --noEmit 2>&1 | tail -1"
    validator: "empty_output"
    optional: true
```

### Data Pipeline (Python/SQL)

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md    # Schema facts, column names, data sources
    - name: infra-report
      type: checks

  tier2:
    - name: etl-rules
      triggers: ["pipeline", "extract", "transform", "load", "ETL"]
      source: rules/etl-rules.md
    - name: query-rules
      triggers: ["SQL", "query", "SELECT", "JOIN"]
      source: rules/query-rules.md

checks:
  - name: db-accessible
    command: "python3 -c 'import sqlite3; sqlite3.connect(\"data.db\").execute(\"PRAGMA integrity_check\").fetchone()' 2>&1"
    validator: "contains:ok"
  - name: venv-active
    command: "python3 -c 'import pandas; print(pandas.__version__)' 2>&1"
    validator: not_empty
```

### Infrastructure / DevOps

```yaml
tiers:
  tier1:
    - name: core-rules
      source: rules/core-rules.md    # Region mappings, service names, access patterns
    - name: infra-report
      type: checks

  tier2:
    - name: k8s-rules
      triggers: ["kubectl", "pod", "deployment", "helm"]
      source: rules/k8s-rules.md
    - name: terraform-rules
      triggers: ["terraform", "tf", "plan", "apply", "module"]
      source: rules/terraform-rules.md

checks:
  - name: kubectl-context
    command: "kubectl config current-context 2>&1"
    validator: not_empty
  - name: terraform-init
    command: "terraform validate -no-color 2>&1 | tail -1"
    validator: "contains:Success"
    optional: true
```
