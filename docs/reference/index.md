# Reference

Patterns, frameworks, and reusable components for building and evolving
your AI Agent Harness system.

---

## Rules & Frameworks

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg .middle } **[Anti-Hallucination Rules](../rules/anti-hallucination-rules.md)**

    ---

    14 cognitive rules for faithful LLM outputs, organized into 5 phases
    (READ, WRITE, VERIFY x2, SIGN-OFF). Each rule cites peer-reviewed
    research.

-   :material-history:{ .lg .middle } **[Rule Evolution Template](rule-evolution-template.md)**

    ---

    The pattern for turning failures into structural enforcement:
    failure to learning to rule to audit check to hook.

-   :material-file-tree:{ .lg .middle } **[Rule Zero](rule-zero.md)**

    ---

    Every file edit triggers: "Is this scattered information that belongs
    in a consolidated file?" Structurally enforced by `on_edit.py` hook.

</div>

## Patterns

<div class="grid cards" markdown>

-   :material-sync:{ .lg .middle } **[Self-Healing Loop](self-healing-loop.md)**

    ---

    Bidirectional feedback between rules and audit checks. Structurally
    enforced: `cross_check.py` generates write-back suggestions for
    persistent drift. Neither side is a dead end.

-   :material-check-decagram:{ .lg .middle } **[Self-Verification](self-verification.md)**

    ---

    After completing any task, re-run at least one verification command.
    Structurally enforced: `on_stop.py` blocks exit if infra files were
    edited after the last check. "I did it" is not "it's done."

-   :material-clipboard-check:{ .lg .middle } **[Audit Runner](audit-runner.md)**

    ---

    On-demand infrastructure and quality checks. Run standalone or
    integrated with the stop hook. Uses the same validator framework
    as startup checks.

-   :material-swap-horizontal:{ .lg .middle } **[Session Continuity](session-continuity.md)**

    ---

    Persistent backlog and session handoff — pick up where you left off
    across sessions without losing context or forgetting tasks.

</div>

## Guides

<div class="grid cards" markdown>

-   :material-database-sync:{ .lg .middle } **[Data Store Mapping](data-store-mapping.md)**

    ---

    YAML-to-SQLite translation for every construct in the course: config,
    rules, checks, tier2 triggers, backlog, and cross-check.

-   :material-rocket-launch:{ .lg .middle } **[Bootstrapping Guide](bootstrapping-guide.md)**

    ---

    Your first 5 rules in ~15 minutes. Walks through identifying repeated
    mistakes and turning them into tier1 rules that make the hooks useful.

</div>
