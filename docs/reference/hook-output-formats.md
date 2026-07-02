# Hook Output Formats

## Overview

Claude Code hooks support two output mechanisms for injecting context into the agent's conversation. Understanding the difference is critical — using the wrong format causes silent drops.

## Two Output Paths

### 1. Plain Text (stdout)

```python
print("STARTUP GATE: Read tier1 files before responding.")
sys.exit(0)
```

- Injected as a `<user-prompt-submit-hook>` block (UserPromptSubmit hooks) or tool-specific tag
- No JSON required
- Works reliably without any special fields

### 2. JSON `hookSpecificOutput` with `additionalContext`

```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",  # REQUIRED
        "additionalContext": "STARTUP GATE: Read tier1 files."
    }
}))
sys.exit(0)
```

- Injected as a `<system-reminder>` block
- **`hookEventName` is REQUIRED** — without it, the entire `additionalContext` is silently dropped
- Value must match the hook's event type: `"UserPromptSubmit"`, `"PostToolUse"`, or `"PreToolUse"`

### 3. JSON `hookSpecificOutput` with `permissionDecision` (PreToolUse only)

```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "Startup not complete."
    }
}))
sys.exit(0)
```

- Blocks the tool call entirely
- Only valid for PreToolUse hooks

## Comparison

| Feature | Plain text | JSON additionalContext |
|---|---|---|
| Injection tag | `<user-prompt-submit-hook>` | `<system-reminder>` |
| Requires `hookEventName` | No | **Yes** (silent drop without it) |
| Semantic weight to model | Hook feedback | System context |
| Complexity | Simpler | More structured |
| Error mode on mistake | Still shows (wrong format = raw text) | Silent drop (no error, no warning) |

## Required `hookEventName` Values

| Hook Type | `hookEventName` Value |
|---|---|
| UserPromptSubmit | `"UserPromptSubmit"` |
| PostToolUse | `"PostToolUse"` |
| PreToolUse | `"PreToolUse"` |
| Stop | N/A (uses exit codes + plain text) |
| SessionStart | N/A (plain text stdout) |

## The Silent Drop Bug (v1.0.0)

In v1.0.0, all `hookSpecificOutput` dicts with `additionalContext` were missing `hookEventName`. Claude Code validated the JSON, found no `hookEventName`, and silently discarded the `additionalContext`. No error was logged. The `deny()` function in `gate_check.py` worked correctly because it included `hookEventName`.

Fixed in v1.0.1 — credit: [@toughIQ](https://github.com/toughIQ) ([Issue #2](https://github.com/dexmaddy/ai-agent-harness/issues/2)).

## Recommendation

Use JSON `hookSpecificOutput` for context injection — `<system-reminder>` framing gives the message stronger semantic weight. But always include `hookEventName`. If in doubt, plain text stdout is the safer default — it never silently drops.
