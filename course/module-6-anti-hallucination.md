# Module 6: Anti-Hallucination Rules

**Time:** 15 minutes
**Goal:** Understand why LLMs hallucinate in summaries, and deploy 14
research-backed rules to prevent it.

---

## Why This Matters

If you use the agent to summarize documents, generate reports, or extract
information from source data, hallucination is your biggest risk.

**What hallucination looks like in practice:**
- Summary says "v2.11.7" but source says "v2.11.6" (off by one digit)
- Summary says "migration completed" but source only says "migration started"
- Summary adds "which typically occurs when..." — true information that
  isn't in the source (benign hallucination)

**The numbers:**
- the agent's benign hallucination rate: **21.31%** (FaithBench, NAACL 2025)
- Reasoning models hallucinate **4.2x more** on grounded summarization (Vectara HHEM)
- More thinking time = **worse faithfulness** (r = -0.685, Yuan & Zhang 2025)

That last finding is counterintuitive: giving the model more time to
"think" makes it more creative but less faithful to the source.

---

## The 14 Rules in 5 Phases

The rules are in `rules/anti-hallucination-rules.md`. Here's the mental
model for why they're organized into phases:

### Phase 1 — READ (6 rules)

**Problem:** How you read data determines how much is available for synthesis.
LLMs lose information when reading too much at once, holding multiple
entities simultaneously, or writing long after reading.

| Rule | One-Line Summary |
|------|-----------------|
| R1 | Process one entity at a time — never batch |
| R2 | Write immediately after reading — delay = fabrication |
| R3 | Never hold multiple entities in memory at once |
| R12 | If context compacted, re-read before writing |
| R26 | Take section-by-section notes, not one big pass |
| R32 | Write chunked notes before attempting synthesis |

**The key insight:** Most hallucination happens because the LLM no longer
has access to the source details when generating the summary. These rules
keep source data fresh in context.

### Phase 2 — WRITE (2 rules)

**Problem:** The generation step itself introduces hallucination through
interpretive commentary and excessive reasoning.

| Rule | One-Line Summary |
|------|-----------------|
| R30 | No interpretive commentary — report, don't analyze |
| R54 | No extended reasoning for generation — reason only for verification |

**The key insight:** "This likely indicates..." is the hallucination
fingerprint. If the source doesn't say it, the summary shouldn't either.

### Phase 3 — VERIFY PASS 1 (1 rule)

**Problem:** Numbers, versions, and dates are the most commonly
corrupted details — and the easiest to verify.

| Rule | One-Line Summary |
|------|-----------------|
| R50 | Scan every number/version/date against source, character by character |

### Phase 4 — VERIFY PASS 2 (5 rules)

**Problem:** Hallucinations cluster at the end of long outputs (attention
dilution). General knowledge gets mixed with source-specific data.

| Rule | One-Line Summary |
|------|-----------------|
| R25 | Re-verify the last 3 sections specifically |
| R27 | Generate 3-5 verification questions, answer from source independently |
| R29 | Find a supporting quote for every claim, or retract it |
| R46 | Double verification rigor on the last third |
| R47 | If a claim sounds like general knowledge, retract it |

**The key insight:** R29 is the most powerful single rule. "Find a quote
or retract" eliminates most benign hallucination because Claude can't
find a quote for something the source doesn't say.

### Phase 5 — SIGN-OFF

Produce a per-rule checklist before presenting output. Any missing rule
was skipped. Any FAIL must be fixed.

---

## How to Deploy These Rules

### Option A: Include in Tier 1 (recommended for summarization-heavy projects)

```yaml
tiers:
  tier1:
    - name: ah-rules
      source: rules/anti-hallucination-rules.md
      description: "Anti-hallucination rules for faithful summaries"
```

Every session loads the rules. Best if you summarize or extract data
in most sessions.

### Option B: Include in Tier 2 (for occasional summarization)

```yaml
tiers:
  tier2:
    - name: ah-rules
      triggers: ["summarize", "summary", "extract", "report", "analyze"]
      source: rules/anti-hallucination-rules.md
      description: "Anti-hallucination rules"
```

Rules load only when the agent is about to summarize or analyze something.

### Option C: Embed in Prompts (no hooks needed)

If you're not using the hook system, paste the relevant rules directly
into your LLM prompts when asking for summaries.

---

## Exercise: Apply to Your Project

Pick a recent Claude output that had an error (wrong number, inferred
conclusion, unsourced claim). Identify which rule would have caught it:

```
Error: _______________________________________________
Rule that would catch it: R___
Why: _______________________________________________
```

Common mappings:
- Wrong number/version → R50 (post-writing scan)
- "This suggests..." / "Likely because..." → R30 (no interpretation)
- Correct fact not in source → R47 (world knowledge quarantine)
- Error at the end of output → R25/R46 (end-of-output verification)
- Inferred outcome from action → R29 (find quote or retract)

---

## The Counterintuitive Finding

The research consistently shows: **more thinking = worse faithfulness
for generation tasks.** This applies to:

- the agent's extended thinking mode
- Chain-of-thought prompting for summary generation
- Iterative refinement beyond 3-4 rounds

Use reasoning for **verification** (Phases 3-4), not for **generation**
(Phase 2). The summary should be extractive and simple. The verification
should be rigorous and analytical.

---

## Checkpoint

- [ ] Anti-hallucination rules file is in your tier1 or tier2 config
- [ ] You can identify which rule would catch a past error
- [ ] You understand why R29 (quote or retract) is the most powerful rule
- [ ] You understand why reasoning helps verification but hurts generation

---

**Next:** [Module 7 — The Feedback Loop](module-7-feedback-loop.md)
