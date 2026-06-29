# Anti-Hallucination Rules for LLM-Generated Summaries

A research-backed framework of 14 cognitive/process rules that reduce
hallucination in LLM-generated summaries and reports. These rules apply
to ANY summarization task — not just one domain.

Each rule cites the peer-reviewed research that motivates it.

---

## How to Use

Include these rules in your LLM prompts when generating summaries,
reports, or any output that must be faithful to source data. Apply them
in 5 phases: READ → WRITE → VERIFY PASS 1 → VERIFY PASS 2 → SIGN-OFF.

> **Why phases?** LLMs skip rules in the middle of long flat lists
> (U-shaped attention bias). Grouping into phases with distinct goals
> ensures each rule gets attention at the right moment.

---

## Phase 1 — READ (data collection)

### R1: One Entity at a Time
Process one entity end-to-end (read → extract → verify) before moving
to the next. Never batch data collection across entities.

> **Research:** Anthropic reduce-hallucinations guide — "for long
> documents, process sections independently to avoid cross-contamination."
> https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations

### R2: Write Immediately After Reading
Extract/write immediately after reading source data. Never delay —
context compaction causes gap-filling with fabricated details.

> **Research:** StructRAG (ICLR 2025) — delayed synthesis loses
> fine-grained detail as task complexity increases.
> https://arxiv.org/abs/2410.08815

### R3: No Simultaneous Multi-Entity Data
Never hold data for multiple entities in working memory simultaneously.
Entity names from one document get attributed to statements from another.

> **Research:** Galileo AI summarization strategies — cross-entity
> attribution is the #1 hallucination pattern in multi-document summarization.
> https://galileo.ai/blog/llm-summarization-strategies

### R12: Re-Read After Compaction
If context compaction occurs during analysis, re-read the source data
before writing. Never write from post-compaction memory alone.

> **Research:** Lost in the Middle (TACL 2024) — information loss from
> context management is a primary cause of hallucination in long-context tasks.
> https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/

### R26: Section-by-Section Notes
For every entity regardless of size: read and take notes on each section
separately. If context compaction occurs at ANY point, start over. Never
fill in gaps with plausible content.

> **Research:** Context Length Degradation (EMNLP 2025) — even with
> masked irrelevant tokens, 7.9-85% degradation from input length alone.
> https://aclanthology.org/2025.findings-emnlp.1264.pdf

### R32: Chunked Notes Before Synthesis
Use a chunked note-taking approach: read each section and write structured
notes BEFORE synthesizing. Even single-page entities need notes before summary.

> **Research:** "Why Hallucination Happens" — LLM context analysis.
> Prevents the lost-in-the-middle effect.
> https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/

---

## Phase 2 — WRITE (extraction and synthesis)

### R30: No Interpretive Commentary
Keep synthesis source-faithful. Do NOT over-analyze or add interpretive
commentary. Reasoning/analytical modes increase hallucination by 4.2x
on grounded summarization.

- DO: "The migration failed with error X at step Y"
- DON'T: "This likely indicates a deeper architectural incompatibility"

> **Research:** Vectara HHEM benchmark (2026) — reasoning models
> hallucinate significantly more on grounded summarization (GPT-4.1 at
> 5.6% vs o3-pro at 23.3%).
> https://github.com/vectara/hallucination-leaderboard

### R54: No Extended Reasoning for Summary Generation
Never use extended thinking or high reasoning budgets for the final
summary text. Use reasoning ONLY for verification steps. Increasing
reasoning budget actively degrades faithfulness (r = -0.685).

> **Research:** Yuan and Zhang (Dec 2025) — BERTScore vs AlignScore
> correlation shows fundamental tension between fluency and faithfulness.
> https://arxiv.org/pdf/2512.03503

---

## Phase 3 — VERIFY PASS 1 (exact match checks)

### R50: Post-Writing Number/Version/Date Scan
After writing, scan EVERY number, version, date, and quantity. For each:
find the exact source value, compare character-by-character. Fix any
difference — even one digit.

Examples to catch:
- "172.17.14.115" vs "172.17.14.15" (dropped digit)
- "v2.11.6" vs "v2.11.7" (version off by one)
- "200Gi" vs "200GB" (wrong unit)
- "3 items" vs "4 items" (wrong count)

> **Research:** HDM-4B-RL (AAAI 2025) — diagnostic paradigm includes
> localization and explainability alongside detection.
> https://arxiv.org/html/2601.09734

---

## Phase 4 — VERIFY PASS 2 (scoring, attribution, retraction)

### R25: Re-Verify Last 3 Sections
Hallucinations are most likely toward the end of generated text.
After writing, specifically re-verify the last 3 sections against source.

> **Research:** "Hallucinate at the Last in Long Response Generation"
> (arXiv 2505.15291, 2025) — faithfulness drops below 0.70 at 45
> sentences from 8K context.

### R27: Independent Verification Questions
After drafting, generate 3-5 verification questions about key claims.
Answer each by re-checking the source INDEPENDENTLY from the draft.
If any answer contradicts the draft, revise before presenting.

CRITICAL: Verification must be in a separate context from the draft.
Models repeat their own hallucinations when verifying in the same context.

> **Research:** Chain-of-Verification (CoVe) — Dhuliawala et al., ACL
> Findings 2024. Factor+revise achieves 28% FactScore improvement and
> 77% reduction in hallucinated entities.
> https://aclanthology.org/2024.findings-acl.212/

### R29: Find Supporting Quote or Retract
After writing each section, find a supporting quote from the source for
EVERY factual claim. If no supporting quote exists, RETRACT the claim
entirely — do not keep it with softened language. Either it's in the
source or it's not in the output.

> **Research:** Anthropic reduce-hallucinations guide — "have Claude
> verify each claim by finding a supporting quote. If it cannot find
> one, it must retract the claim."
> https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations
>
> FaithBench (NAACL 2025) — the agent's benign hallucination rate is
> 21.31%, the highest among tested models.
> https://arxiv.org/abs/2410.13210

### R46: Double Verification on Last Third
The last third of every output must be verified with DOUBLE the rigor
of the first third. For each claim in the final third, find the exact
supporting quote — not just confirm it "sounds right."

> **Research:** Hallucination Survey (ACM TOIS 2025) — documents the
> mechanism: localized attention + attention dilution across positions.
> https://dl.acm.org/doi/10.1145/3703155

### R47: Retract Unsourced General Knowledge
After generating each section, scan for claims that sound like general
knowledge rather than source-specific data. If a claim cannot be traced
to a specific source location, RETRACT it — regardless of whether it's
factually correct. The job is summarization, not education.

- DO: "DNS resolution failure identified (comment #16, A. Example)"
- DON'T: "DNS resolution failure, which typically occurs when the
  VM's DNS configuration doesn't match the target network"

> **Research:** FaithBench (NAACL 2025) — the agent produced the highest
> benign hallucination rate among tested models (21.31%).
> https://arxiv.org/abs/2410.13210

---

## Phase 5 — SIGN-OFF

After completing all phases, produce a per-rule checklist:

```
ANTI-HALLUCINATION SIGN-OFF
R1:  [PASS/FAIL/N/A] One entity at a time
R2:  [PASS/FAIL/N/A] Write immediately after reading
R3:  [PASS/FAIL/N/A] No simultaneous multi-entity data
R12: [PASS/FAIL/N/A] Re-read after compaction
R26: [PASS/FAIL/N/A] Section-by-section notes
R32: [PASS/FAIL/N/A] Chunked notes before synthesis
R30: [PASS/FAIL/N/A] No interpretive commentary
R54: [PASS/FAIL/N/A] No extended reasoning for generation
R50: [PASS/FAIL/N/A] Number/version/date scan
R25: [PASS/FAIL/N/A] Re-verify last 3 sections
R27: [PASS/FAIL/N/A] Independent verification questions
R29: [PASS/FAIL/N/A] Find supporting quote or retract
R46: [PASS/FAIL/N/A] Double verification on last third
R47: [PASS/FAIL/N/A] Retract unsourced general knowledge
```

If any rule shows FAIL, go back and fix it before presenting the output.
If any rule is missing from the sign-off, it was skipped — go back and check it.

---

## Key Insight: More Reasoning = Worse Faithfulness

The most counterintuitive finding across this research: **giving the LLM
more thinking time makes summaries less faithful** (r = -0.685, p = 0.014).
The model prioritizes fluency and coherence over source fidelity, adding
plausible-but-unsourced enrichment. Use reasoning for verification, never
for generation.

---

## References

1. Anthropic — Reduce Hallucinations Guide (2024)
   https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations
2. StructRAG — ICLR 2025
   https://arxiv.org/abs/2410.08815
3. Lost in the Middle — Liu et al., TACL 2024
   https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/
4. Chain-of-Verification (CoVe) — Dhuliawala et al., ACL Findings 2024
   https://aclanthology.org/2024.findings-acl.212/
5. FaithBench — NAACL 2025
   https://arxiv.org/abs/2410.13210
6. Vectara HHEM Hallucination Leaderboard (2026)
   https://github.com/vectara/hallucination-leaderboard
7. Hallucinate at the Last — arXiv 2505.15291 (2025)
8. Hallucination Survey — ACM TOIS 2025
   https://dl.acm.org/doi/10.1145/3703155
9. Context Length Degradation — EMNLP 2025
   https://aclanthology.org/2025.findings-emnlp.1264.pdf
10. HDM-4B-RL — AAAI 2025
    https://arxiv.org/html/2601.09734
11. Yuan and Zhang — Dec 2025
    https://arxiv.org/pdf/2512.03503
12. Galileo AI — LLM Summarization Strategies
    https://galileo.ai/blog/llm-summarization-strategies
