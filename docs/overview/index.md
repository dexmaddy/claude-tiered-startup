# Agentic AI Tiered Startup Architecture

A progressive, hook-based system that ensures AI agent sessions start with
the right context loaded, enforced structurally — not by hoping the agent reads
your instructions carefully.

## What This Solves

| Problem | Symptom | Solution |
|---------|---------|----------|
| **Context waste** | Loading 3000 lines of rules for a typo fix | Tiered loading — essential rules always, specialized on-demand |
| **Rule drift** | Instructions say "58 rules" but there are 62 | Drift detection — automatic expected vs actual checks |
| **Startup chaos** | Agent skips rule files, starts working immediately | Structural gates — tools blocked until rules are loaded |

## Quick Setup

```bash
git clone https://github.com/dexmaddy/agentic-ai-tiered-startup.git
cd agentic-ai-tiered-startup
python3 setup.py
```

The interactive wizard configures everything for your agent platform and project.

## Explore

- **New here?** Start with [The Problem](overview/the-problem.md) to understand why this exists
- **Want to build?** Jump to the [Course](course/README.md) — 8 modules, ~2.5 hours
- **Just want code?** Run `python3 setup.py` and follow the prompts
- **Visual learner?** Download the [slide deck](slides.md)
