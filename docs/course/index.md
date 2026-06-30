# Course

A structured, self-paced course for building reliable AI agent sessions —
from startup through work to shutdown. 8 modules, ~2.5 hours total.
Each module builds on the previous one.

---

## Foundations

<div class="grid cards" markdown>

-   :material-alert-circle:{ .lg .middle } **[Module 1: The Problem](module-1-the-problem.md)**

    ---

    Why unmanaged AI sessions waste tokens and produce unreliable results.
    Diagnose the specific pain points in your own project.

    **Time:** 10 minutes

-   :material-sitemap:{ .lg .middle } **[Module 2: Architecture](module-2-architecture.md)**

    ---

    The 5-hook engine, manifest/sentinel state management, and 6 key
    design decisions. Build the mental model before writing code.

    **Time:** 15 minutes

</div>

## Hands-On

<div class="grid cards" markdown>

-   :material-hammer-wrench:{ .lg .middle } **[Module 3: First Hook](module-3-first-hook.md)**

    ---

    Build a working Level 1 system — SessionStart hook that runs infra
    checks and generates tier1 files from a YAML config.

    **Time:** 20 minutes

-   :material-gate:{ .lg .middle } **[Module 4: Adding Gates](module-4-gates.md)**

    ---

    Add structural enforcement — PreToolUse blocks tools until rules are
    loaded, UserPromptSubmit injects gate messages and catches infra FAILs.

    **Time:** 20 minutes

-   :material-cog:{ .lg .middle } **[Module 5: Advanced](module-5-advanced.md)**

    ---

    On-demand tier2 loading with keyword triggers, drift detection with
    auto-heal, stop hook with retry loop, and session continuity.

    **Time:** 20 minutes

</div>

## Deep Dives

<div class="grid cards" markdown>

-   :material-brain:{ .lg .middle } **[Module 6: Anti-Hallucination](module-6-anti-hallucination.md)**

    ---

    14 research-backed cognitive rules for faithful LLM outputs, organized
    into 5 phases to counter U-shaped attention bias.

    **Time:** 15 minutes

-   :material-sync:{ .lg .middle } **[Module 7: Feedback Loop](module-7-feedback-loop.md)**

    ---

    Turn failures into structural enforcement: failure to learning to
    rule to audit check to hook. The system learns from its own mistakes.

    **Time:** 15 minutes

-   :material-trophy:{ .lg .middle } **[Module 8: Capstone](module-8-capstone.md)**

    ---

    Wire everything together for your project. Deploy the full system,
    run the smoke test, and verify end-to-end.

    **Time:** 30 minutes

</div>

---

## Prerequisites

- An AI coding agent installed (Claude Code, Cursor, Windsurf, Aider, or custom)
- A project you actively use an AI agent with (any language/framework)
- Basic familiarity with JSON and Python (reading, not writing)

**Visual companion:** Download the [slide deck](../slides.md) to follow along with diagrams.

**Just want to deploy?** Skip the course — run `python3 setup.py` and the
interactive wizard handles everything in 2 minutes.
