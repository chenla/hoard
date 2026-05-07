# Installation Guide

Three components, each optional. Use what fits your workflow.

## 1. Hoard CLI (required)

The command-line tool for creating, compiling, and querying your hord.

```bash
# Requires Python 3.10+ and Git
pipx install hoard-git
```

Don't have pipx? `sudo apt install pipx` (Debian/Ubuntu) or `pip install pipx`.

Verify:

```bash
hord --version
```

### From source

```bash
git clone https://github.com/chenla/hoard
cd hoard
pip install -e .
```

## 2. Emacs reader (optional)

[hord.el](https://github.com/chenla/hord.el) — card browser, agenda, triage, blob management.

```bash
git clone https://github.com/chenla/hord.el ~/proj/hord.el
```

Add to your init:

```elisp
(add-to-list 'load-path "~/proj/hord.el/")
(require 'hord)

;; Point to your hord
(setq hord-root "~/proj/hord/")

;; Scratch pad location
(setq hord-scratch-directory "~/path/to/scratch/")
(setq hord-scratch-inbox-file "~/path/to/mobile-inbox.org")
```

Requires Emacs 28.1+ and a compiled hord (`hord compile`).

Key commands:
- `C-c W f` — find card
- `C-c W l` — list all cards
- `C-c W A` — agenda (tasks + calendar)
- `C-c W s` — daily scratch pad

See the [hord.el README](https://github.com/chenla/hord.el) for full documentation.

### Google Calendar integration (optional)

The agenda can pull Google Calendar events. Requires:

1. A Google Cloud project with Calendar API enabled
2. OAuth credentials (desktop app type) with `calendar.readonly` scope
3. `http://localhost:8085` as an authorized redirect URI

Place the OAuth keys JSON alongside the fetch script and run the
one-time auth flow. See `gcal-fetch.py` in the hord.el repo.

### Readwise integration (optional)

Readwise highlights are imported into scratch on open. Requires
a Readwise API token. See `readwise-fetch.py` in the hord.el repo.

## 3. MCP server (optional)

Gives Claude (or any MCP-compatible agent) direct access to your hord.

Add to your Claude Code config (`~/.claude/settings.json` or project `.claude.json`):

```json
{
  "mcpServers": {
    "hoard": {
      "command": "/path/to/python",
      "args": ["-m", "hord.mcp_server"],
      "env": { "HORD_ROOT": "/absolute/path/to/your/hord" }
    }
  }
}
```

If using a virtualenv:

```json
{
  "mcpServers": {
    "hoard": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "hord.mcp_server"],
      "env": { "HORD_ROOT": "/absolute/path/to/your/hord" }
    }
  }
}
```

Tools available: `query`, `search`, `list_entities`, `status`,
`compile`, `vocab_lookup`, `read_content`, `new_card`, `capture`.

## Your first hord

Once the CLI is installed:

```bash
mkdir my-knowledge && cd my-knowledge
git init
hord init --name "my-knowledge"
hord new "First Card" -t con
hord compile
hord query First_Card
```

See [Quick Start](QUICKSTART.md) for a fuller walkthrough.
