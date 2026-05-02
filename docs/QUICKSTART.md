# Quick Start

Install Hoard, run the demo, create your first card. Three minutes.

## Install

```bash
# Requires Python 3.11+ and Git
pipx install hoard-git
```

Don't have pipx? `sudo apt install pipx` (Debian/Ubuntu) or `pip install pipx`.

## Try the demo

```bash
git clone https://github.com/chenla/hoard
cd hoard/examples/tps-hord

hord query Kanban                 # view a card's relationships
hord query Toyota_Production_System--4   # a richer example
hord search "production"          # keyword search
hord tags                         # see all tags
hord status                       # check for stale metadata
hord web                          # browse in your browser (port 7750)
```

## Create your own hord

```bash
mkdir my-knowledge && cd my-knowledge
git init
hord init --name "my-knowledge"
```

## Create a card

```bash
hord new "Kanban" -t con          # concept card
hord new "Taiichi Ohno" -t per    # person card
hord new "My Paper" -t wrk        # work (book, paper, etc.)
hord new                          # interactive mode — prompts for everything
```

Cards are org-mode files by default. Use `hord init --format md` for markdown.

## Capture a quick thought

```bash
hord capture "Kanban is a pull system" -t "lean manufacturing"
hord capture "Interesting paper on X" -s reading -t research
```

Captures create `wh:cap` cards in `capture/` with immediate quad compilation.

## Build relationships

```bash
hord link add Kanban BT Toyota_Production_System   # Kanban is narrower than TPS
hord link add Kanban UF "看板"                       # 看板 is an alias
hord link show Kanban                               # see all relations
hord link suggest Kanban                            # find unlinked related cards
```

## Add a reference file

```bash
hord add paper.pdf -k scott:1998seeing -t "Seeing Like a State" -a "James C. Scott"
```

Files go to `lib/blob/` with citekey-based names. A `wh:wrk` card is created automatically.

## Compile and check

```bash
hord compile          # parse cards → generate quads + index
hord status           # find stale metadata
hord query <card>     # inspect any entity
```

## What's next

- **Import existing notes:** `hord import ~/path/to/notes` — auto-detects Obsidian, Logseq, org-roam, Dendron, Notion, or plain markdown. See [Migration Guide](MIGRATION.md).
- **Mobile capture:** `hord mobile serve` — HTTP capture from your phone. See `hord mobile setup`.
- **Browse without Emacs:** `hord web` — local web interface for browsing and creating cards.
- **AI integration:** Configure the MCP server for Claude or any MCP-compatible agent. See [MCP Tools spec](spec-mcp-tools.md).
- **Understand the architecture:** Read [Understanding Hoard](INTRODUCTION.md) for the five-level explanation.
