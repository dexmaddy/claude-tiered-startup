# Agentic AI Tiered Startup Architecture — Mini Course

A structured, self-paced course for building reliable AI agent sessions
that start with the right context, enforced structurally.

## Who This Is For

- AI agent users whose sessions start inconsistently
- Teams whose agents forget project rules mid-conversation
- Anyone who has written "the agent must read X first" in your instructions file and
  watched the agent ignore it

## What You'll Learn

By the end of this course, you will:
1. Understand why unmanaged AI sessions waste tokens and produce unreliable results
2. Build a tiered loading system that loads only what's needed per session
3. Add structural gates that enforce rule loading before any work begins
4. Write anti-hallucination rules backed by peer-reviewed research
5. Create a self-improving feedback loop from failures to enforcement

## Course Structure

| Module | Title | Time | What You'll Build |
|--------|-------|------|-------------------|
| 1 | [The Problem](module-1-the-problem.md) | 10 min | Problem diagnosis for your own project |
| 2 | [Architecture Concepts](module-2-architecture.md) | 15 min | Mental model of the 4-hook system |
| 3 | [Your First Startup Hook](module-3-first-hook.md) | 20 min | Working Level 1: manifest + tier1 files |
| 4 | [Adding Gates](module-4-gates.md) | 20 min | Level 2: structural enforcement |
| 5 | [On-Demand Loading & Drift Detection](module-5-advanced.md) | 20 min | Level 3-4: tier2 triggers, cross-check, stop hook |
| 6 | [Anti-Hallucination Rules](module-6-anti-hallucination.md) | 15 min | 14-rule framework for faithful outputs |
| 7 | [The Feedback Loop](module-7-feedback-loop.md) | 15 min | Failure → rule → enforcement pipeline |
| 8 | [Capstone: Wire It All Together](module-8-capstone.md) | 30 min | Full working system for your project |

**Total time: ~2.5 hours**

**Visual companion:** Download the [slide deck (PDF)](../slides/Structural_AI_Agent_Enforcement.pdf)
to follow along with diagrams for each level.

## Prerequisites

- An AI coding agent installed (Claude Code, Cursor, Windsurf, Aider, or any custom agent)
- A project you actively use an AI coding agent with (any language/framework)
- Basic familiarity with JSON and Python (reading, not writing)
- No database required — the setup wizard lets you choose YAML files, SQLite, or PostgreSQL

**Quick setup without the course:** If you just want to deploy, run `python3 setup.py`
in the repo — the interactive wizard handles everything in 2 minutes.

## How to Use This Course

**Option A — Sequential:** Work through modules 1-8 in order. Each module
builds on the previous one. Best for first-time learners.

**Option B — Pick what you need:**
- "My sessions are inconsistent" → Start with Modules 1-3
- "the agent ignores my rules" → Modules 2 + 4
- "My summaries have errors" → Module 6
- "I keep fixing the same mistakes" → Module 7
- "I want the full system" → All modules, then Module 8 capstone

## Quick Assessment

Before starting, rate your current pain level (1-5):

```
[ ] Sessions start differently each time               ___/5
[ ] The agent forgets rules I've written in your instructions file      ___/5
[ ] I correct the same mistakes across sessions         ___/5
[ ] LLM outputs contain unsourced or inaccurate claims  ___/5
[ ] I spend tokens loading context that isn't needed    ___/5
```

If your total is 15+, do the full course.
If 10-14, start at Module 3.
If under 10, skip to Module 6 or 7 for targeted improvement.
