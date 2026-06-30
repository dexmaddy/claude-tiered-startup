# What It Does For You

A complete map of capabilities — what fires, when, and what it prevents.

---

## The Full Picture

```mermaid
graph TB
    subgraph START ["<b>Session Start</b>"]
        direction TB
        S1["Infrastructure Checks<br/><small>DB, git, venv, custom commands</small>"]
        S2["Tiered Loading<br/><small>Tier 1 always, Tier 2 on-demand</small>"]
        S3["State Tracking<br/><small>Manifest + sentinel per session</small>"]
    end

    subgraph GATE ["<b>Startup Gate</b>"]
        direction TB
        G1["Tool Blocking<br/><small>Non-Read tools denied until<br/>rules are in context</small>"]
        G2["Context Reset Detection<br/><small>Detects /clear, re-triggers startup</small>"]
        G3["Prompt Health Warnings<br/><small>Warns at configurable thresholds</small>"]
    end

    subgraph WORK ["<b>During Work</b>"]
        direction TB
        W1["Rule Zero<br/><small>Every edit scanned for<br/>scattered information</small>"]
        W2["Drift Detection<br/><small>Expected vs actual, auto-heal,<br/>bounded 2 passes</small>"]
        W3["Tier 2 Triggers<br/><small>Keywords in tool calls load<br/>task-specific rules</small>"]
    end

    subgraph STOP ["<b>Session End</b>"]
        direction TB
        E1["Self-Verification<br/><small>Blocks exit if fixes<br/>not re-checked</small>"]
        E2["Clean Shutdown<br/><small>Repos, transcript, audit<br/>must pass</small>"]
        E3["Session Continuity<br/><small>Backlog + handoff persist<br/>across sessions</small>"]
    end

    START --> GATE --> WORK --> STOP

    style START fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    style GATE fill:#fff3e0,stroke:#ef6c00,color:#e65100
    style WORK fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    style STOP fill:#fce4ec,stroke:#c62828,color:#b71c1c

    style S1 fill:#fff,stroke:#4caf50
    style S2 fill:#fff,stroke:#4caf50
    style S3 fill:#fff,stroke:#4caf50
    style G1 fill:#fff,stroke:#ff9800
    style G2 fill:#fff,stroke:#ff9800
    style G3 fill:#fff,stroke:#ff9800
    style W1 fill:#fff,stroke:#2196f3
    style W2 fill:#fff,stroke:#2196f3
    style W3 fill:#fff,stroke:#2196f3
    style E1 fill:#fff,stroke:#f44336
    style E2 fill:#fff,stroke:#f44336
    style E3 fill:#fff,stroke:#f44336
```

!!! note "Cross-cutting capabilities"
    Three capabilities apply across all phases and aren't shown above:

    - **Anti-Hallucination Rules** — 59 rules in 5 phases for source-faithful LLM outputs
    - **Feedback Loop** — failures become rules, rules become checks, checks become hooks
    - **Sensitive Data Prevention** — pre-commit hook + consistency checker block personal data

---

## Lifecycle: When Each Capability Fires

```mermaid
graph TD
    subgraph START ["Session Start"]
        A["SessionStart hook"] --> B["Run infrastructure checks"]
        B --> C["Generate Tier 1 + Tier 2 files"]
        C --> D["Write manifest + sentinel"]
    end

    subgraph GATE ["Startup Gate"]
        D --> E["UserPromptSubmit hook"]
        E --> F{"Tier 1 files<br/>all read?"}
        F -->|NO| G["List remaining files"]
        F -->|YES| H["Unblock tools"]
        H --> I["Cross-check runs once"]
    end

    subgraph WORK ["During Work"]
        I --> J["PreToolUse hook"]
        J --> K{"Tool blocked?"}
        K -->|Tier 2 keyword| L["Load additional context"]
        K -->|Allowed| M["Tool executes"]
        M --> N["PostToolUse hook"]
        N --> O["Rule Zero scan"]
        N --> P["Edit count + save reminder"]
    end

    subgraph STOP ["Session End"]
        Q["Stop hook"] --> R{"Self-Verification:<br/>fixes re-checked?"}
        R -->|NO| S["Exit code 2: retry"]
        S --> T["Agent fixes issue"]
        T --> Q
        R -->|YES| U{"Repos clean?<br/>Transcript saved?<br/>Audit passes?"}
        U -->|NO| S
        U -->|YES| V["Exit 0: session ends"]
    end

    M --> Q

    style START fill:#e8f5e9
    style GATE fill:#fff3e0
    style WORK fill:#e3f2fd
    style STOP fill:#fce4ec
```

---

## Capability Reference

| Capability | What It Does | Hook / Component | Level |
|-----------|-------------|-----------------|-------|
| **Infrastructure Checks** | Validates DB, git, venv, custom commands at startup | `on_session_start.py` | 1 |
| **Tiered Loading** | Loads core rules always, task-specific rules on demand | `on_session_start.py` | 1 |
| **Manifest + Sentinel** | Tracks session state, file reads, stage progression | `on_session_start.py` | 1 |
| **Gate Enforcement** | Blocks non-Read tools until Tier 1 is loaded | `gate_check.py` | 2 |
| **Prompt Health** | Warns at configurable prompt count thresholds | `on_prompt_submit.py` | 2 |
| **Context Reset Detection** | Detects `/clear` and re-triggers startup | `on_prompt_submit.py` | 2 |
| **Tier 2 Keyword Triggers** | Scans tool inputs for task keywords, loads matching files | `gate_check.py` | 3 |
| **Drift Detection** | Compares expected counts against live state | `cross_check.py` | 3 |
| **Auto-Heal** | Fixes safe drift items automatically (bounded, 2 passes) | `cross_check.py` | 3 |
| **Write-Back Suggestions** | Proposes manifest updates for persistent drift | `cross_check.py` | 3 |
| **Rule Zero** | Scans edited files for scattered content, warns to consolidate | `on_edit.py` | 4 |
| **Edit Tracking** | Counts edits, periodic save reminders | `on_edit.py` | 4 |
| **Self-Verification** | Blocks exit if infrastructure was edited but not re-checked | `on_stop.py` | 4 |
| **Clean Shutdown** | Requires clean repos, transcript, audit pass before exit | `on_stop.py` | 4 |
| **Session Continuity** | Persistent backlog (JSON or DB) loaded at startup | `backlog.json` / DB | 4 |
| **No-Truncation** | Verifies DB stores weren't silently truncated | `on_stop.py` | 4 |
| **Audit Runner** | On-demand infrastructure checks, same validators as startup | `audit.py` | 4 |
| **Sensitive Data Scan** | Pre-commit hook + consistency checker block personal data | `pre-commit` + `consistency_check.py` | 4 |
| **Anti-Hallucination Rules** | 59 rules in 5 phases for faithful LLM outputs | `rules/` + DB | Any |
| **Feedback Loop** | Failure → Learning → Rule → Check → Hook evolution | Pattern | Any |

---

## What Problem Does Each Capability Solve?

!!! tip "Read this column when deciding what to enable"

| Capability | Without It | With It |
|-----------|-----------|---------|
| Gate Enforcement | Agent starts working before loading rules — applies defaults, not your conventions | Tools blocked until rules are in context — every session starts with full knowledge |
| Rule Zero | Information scatters across files and conversations, lost at session end | Every edit is categorized and routed — nothing gets lost |
| Self-Verification | Agent says "done" but the fix wasn't tested | Exit blocked until verification re-runs — "done" means verified |
| Drift Detection | Config says 3 rules but you have 5 — silent mismatch grows | Expected vs actual compared every session — drift caught early |
| Anti-Hallucination | LLM adds plausible but unsourced details to summaries | 59 rules enforce source-faithful extraction — retract if no quote |
| Feedback Loop | Same mistakes repeat across sessions | Each failure becomes a rule, each rule becomes a check — system learns |
| Session Continuity | User re-explains context every session | Agent picks up where last session left off — backlog persists |
| Sensitive Data Scan | Personal data accidentally committed to public repos | Pre-commit hook + scanner block matches before they reach git |

---

## Adoption Levels

Start with Level 1 and grow as needed. Each level adds capabilities without
breaking previous ones.

```mermaid
graph LR
    L1["Level 1<br/>Manifest Only<br/><i>voluntary compliance</i>"] --> L2["Level 2<br/>+ Gates<br/><i>tools blocked until<br/>rules loaded</i>"]
    L2 --> L3["Level 3<br/>+ Tier 2 + Drift<br/><i>on-demand loading,<br/>drift detection</i>"]
    L3 --> L4["Level 4<br/>Full Architecture<br/><i>Rule Zero, Self-Verify,<br/>stop hook, audit</i>"]

    style L1 fill:#e8f5e9,color:#1b5e20
    style L2 fill:#fff3e0,color:#e65100
    style L3 fill:#e3f2fd,color:#0d47a1
    style L4 fill:#f3e5f5,color:#4a148c
```

---

**Ready to set it up?** Run the [Setup Wizard](../reference/setup-wizard.md)
to generate your configuration at your chosen level.
