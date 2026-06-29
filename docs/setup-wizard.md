# Setup Wizard

The fastest way to get started. Run the interactive wizard and it handles everything.

## Quick Start

```bash
git clone https://github.com/dexmaddy/agentic-ai-tiered-startup.git
cd agentic-ai-tiered-startup
python3 setup.py
```

## What the Wizard Does

1. **Asks your platform** — Claude Code, Cursor, Windsurf, Aider, or custom
2. **Asks your data store** — YAML/JSON files, SQLite, or PostgreSQL
3. **Asks your enforcement level** — Level 1 (manifest only) through Level 4 (full architecture)
4. **Asks project details** — anti-hallucination rules, persistent backlog

Then it:

- Copies the right hook scripts to your project
- Generates config files for your chosen data store
- Creates sample rules you can customize
- Wires the settings file for your agent platform
- Installs any needed dependencies

## Non-Interactive Mode

For CI/CD or scripted setup:

```bash
python3 setup.py --non-interactive \
  --platform claude \
  --store sqlite \
  --level 2 \
  --dir /path/to/your/project
```

### Options

| Flag | Values | Default |
|------|--------|---------|
| `--platform` | `claude`, `cursor`, `windsurf`, `aider`, `custom` | `claude` |
| `--store` | `yaml`, `sqlite`, `postgres` | `yaml` |
| `--level` | `1`, `2`, `3`, `4` | `2` |
| `--dir` | path to project | current directory |
| `--no-ah-rules` | skip anti-hallucination rules | included by default |
| `--no-backlog` | skip persistent backlog | included by default |
