# Overview

Understand the problem this architecture solves, how it works, and the
design decisions behind it.

---

## Start Here

<div class="grid cards" markdown>

-   :material-checkbox-multiple-marked:{ .lg .middle } **[What It Does For You](capabilities.md)**

    ---

    The complete capability map — 20 capabilities across startup, work,
    and shutdown. See what each one prevents and which level enables it.

</div>

## Concepts

<div class="grid cards" markdown>

-   :material-alert-circle:{ .lg .middle } **[The Problem](the-problem.md)**

    ---

    Why unmanaged AI agent sessions fail: context waste, rule drift, and
    startup chaos. The case for structural enforcement over written instructions.

-   :material-sitemap:{ .lg .middle } **[Architecture](architecture.md)**

    ---

    The 4-hook engine (SessionStart, PreToolUse, UserPromptSubmit, Stop),
    manifest/sentinel state management, and how tiers work together.

</div>

## Implementation

<div class="grid cards" markdown>

-   :material-stairs:{ .lg .middle } **[Implementation Levels](levels.md)**

    ---

    Four progressive levels from voluntary compliance (Level 1) to full
    structural enforcement with stop-hook cleanup (Level 4). Start simple,
    add enforcement as needed.

-   :material-database-cog:{ .lg .middle } **[Data Store & Platforms](data-and-platforms.md)**

    ---

    YAML files vs SQLite vs PostgreSQL — when to use each. Platform
    adaptation guides for Claude Code, Cursor, Windsurf, Aider, and custom agents.

</div>

## Insights

<div class="grid cards" markdown>

-   :material-lightbulb:{ .lg .middle } **[Lessons Learned](lessons-learned.md)**

    ---

    Eight hard-won insights from building this system: documenting is not
    doing, exit codes lie, gate don't nag, more reasoning = worse faithfulness,
    and more.

-   :material-presentation:{ .lg .middle } **[Slide Deck](../slides.md)**

    ---

    10-slide visual companion covering the problem, 4-hook engine, tiering
    strategy, and all 4 levels. Use alongside these pages or share with
    your team.

</div>
