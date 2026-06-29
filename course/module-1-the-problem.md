# Module 1: The Problem

**Time:** 10 minutes
**Goal:** Understand the three problems that unmanaged AI sessions create,
and diagnose which ones affect your project.

---

## The Three Problems

### Problem 1: Context Waste

Every AI agent session has a finite context window. Everything the agent
reads — files, command output, your messages — consumes tokens from that
window. When the window fills, older content is compressed or lost.

**The waste pattern:**
```
Session starts
  → the agent reads 3000 lines of rules (costs ~4K tokens)
  → User asks to fix a typo
  → 4K tokens wasted on rules that weren't needed
```

Multiply this by every session, and you're burning significant context
budget on rules that only matter 20% of the time.

**The fix:** Load rules in tiers — essential rules always, specialized
rules only when the task needs them.

### Problem 2: Rule Drift

Your project has facts that change: table counts, API endpoints, version
numbers, team conventions. These facts live in your instructions file, memory files,
or rule documents.

**The drift pattern:**
```
Week 1: CLAUDE.md says "58 rules in the system"
Week 3: You added 4 more rules
Week 5: CLAUDE.md still says "58 rules"
         The agent trusts the stale number
         References the wrong rule count in outputs
```

Drift is invisible until it causes a mistake. By then, you don't know
how many other facts are stale.

**The fix:** Generate rule files from a single source of truth (config
file or database) at session start. Detect drift automatically.

### Problem 3: Startup Chaos

You write "the agent must read these files at startup" in your instructions file. The agent
reads it. Then:

- Reads 4 of 6 files and starts working
- Reads the files but in the wrong order
- Skips reading entirely because the user asked a question first
- Reads the files but context compaction later loses them

**The chaos pattern:**
```
CLAUDE.md: "Always read rules/core.md before any task"
Reality:   the agent read it in 3 of 10 sessions
           In 2 sessions, it was lost to context compaction
           In 5 sessions, the agent started working immediately
```

Writing instructions in a markdown file is documentation, not enforcement.
There's no mechanism to guarantee the agent follows them.

**The fix:** Structural enforcement — hooks that physically block the agent
from using tools until the rules are loaded.

---

## Diagnose Your Project

### Exercise 1: Count the Waste (5 minutes)

Open your project instructions or project instructions. Estimate:

1. **Total lines of instructions:** ___
2. **Lines needed for a typical session:** ___
3. **Waste ratio:** (1 - line 2/line 1) × 100 = ____%

If your waste ratio is over 40%, tiered loading will save significant
context budget.

### Exercise 2: Find the Drift (3 minutes)

Search your project instructions for any numbers, versions, or counts:

```bash
grep -E "[0-9]+" CLAUDE.md | head -20
```

For each number: is it still correct? Check the actual source.

Common drift candidates:
- Rule counts ("58 rules" → actually 62 now)
- API endpoints ("v2" → project moved to v3)
- Team conventions ("use Jest" → migrated to Vitest)

### Exercise 3: Test the Enforcement (2 minutes)

Start a fresh AI agent session and immediately ask a question
(don't mention startup or rules). Does the agent:

- [ ] Read your rule files before answering? → You're already enforced
- [ ] Answer directly, skipping rule files? → You need gates
- [ ] Read some files but not all? → You need tracking + gates

---

## Key Takeaway

| Problem | Symptom | Solution |
|---------|---------|----------|
| Context waste | High token usage, rules loaded but not needed | Tiered loading (Module 3) |
| Rule drift | Stale numbers in instructions, wrong facts in output | Generated files + drift detection (Module 5) |
| Startup chaos | Inconsistent behavior across sessions | Structural gates (Module 4) |

Most projects have all three. The architecture in this course solves
them together — each module adds a layer of defense.

---

**Next:** [Module 2 — Architecture Concepts](module-2-architecture.md)
