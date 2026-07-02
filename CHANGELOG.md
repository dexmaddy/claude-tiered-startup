# Changelog

All notable changes to this project will be documented in this file.

## [v1.0.1] — 2026-07-02

### Fixed

- **hookEventName missing from additionalContext outputs** — All `hookSpecificOutput` dicts that contain `additionalContext` now include the required `hookEventName` field. Without it, Claude Code silently dropped the injected context. ([#2](https://github.com/dexmaddy/ai-agent-harness/issues/2))
  - `hooks/on_prompt_submit.py` — context reset gate, startup incomplete gate, prompt health warnings (3 locations)
  - `hooks/on_edit.py` — Rule Zero warnings, save reminders
  - `hooks/gate_check.py` — stale facts advisory

### Added

- `docs/reference/hook-output-formats.md` — documents the two hook output mechanisms (plain text vs JSON `additionalContext`), the `hookEventName` requirement, and comparison table

### Credit

- Fix by [@toughIQ](https://github.com/toughIQ) (Chris Tawfik)

## [v1.0.0] — 2026-06-30

Initial release. Hook-based framework for reliable AI agent sessions:

- **Level 1:** SessionStart hook — infra checks, DB-to-file generation, manifest
- **Level 2:** Startup gates — PreToolUse blocks until Tier 1 read, UserPromptSubmit nags
- **Level 3:** Tier 2 on-demand loading via keyword triggers
- **Level 4:** PostToolUse — Rule Zero, save reminders, ripple check, sync
- **Level 5:** Stop hook — session summary, transcript save, clean repos
- Anti-hallucination rules, audit runner, self-verification, context reset detection
- MkDocs course with 8 modules
