# Hoard

**Semantic metadata overlays for git repositories.**

Hoard adds a `.hord/` directory to any git repo — structured metadata that sits alongside your content, versioned by git. Think `.git/` but for knowledge structure.

## Try it

```bash
git clone https://github.com/chenla/hoard
cd hoard
pipx install .             # or: pip install -e .
cd examples/tps-hord
hord query Kanban
```

Output:

```
════════════════════════════════════════════════════════════
  Kanban—4
  d4e5f6a7-1001-4000-8000-000000000011
════════════════════════════════════════════════════════════

          TYPE  wh:con
            TT  Concept—8  (852a6e49…)
            BT  Toyota Production System—4  (c348132e…)
            RT  Just-in-Time Manufacturing—4  (d4e5f6a7…)
            RT  Muda—4  (d4e5f6a7…)
            UF  看板
            UF  Signboard system
            PT  Kanban—4

────────────────────────────────────────────────────────────
  Incoming links:

  Taiichi Ohno—7  (e5f6a7b8…)
    ← RT
  Heijunka—4  (d4e5f6a7…)
    ← RT
  Toyota Production System—4  (c348132e…)
    ← NT
  ...
```

One query shows: typed hierarchy (BT/NT), related concepts (RT), multilingual aliases (UF), and incoming links from people and sub-concepts — all resolved from structured quads, not scraped from prose.

The `—4` suffix means "concept" (type code 4). Person cards end in `—7`, works in `—6`. You can tell what something is at a glance.

## What problem does this solve?

You have notes — maybe hundreds, maybe thousands. Half your links are broken because you renamed a file. You can't tell which notes are stale. An AI reading your notes has to guess at structure because there isn't any.

Systems like Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) store knowledge as markdown with inline links. That works until it doesn't:

| | Flat Wiki | Hoard |
|---|---|---|
| **Identity** | Filenames (break on rename) | UUIDs (stable forever) |
| **Relationships** | Inline `[[links]]` (untyped) | Typed predicates (BT, NT, RT) |
| **Vocabulary** | Ad hoc tags | Formal thesaurus with equivalence mappings |
| **Multilingual** | Separate pages per language | `UF` maps equivalent terms across languages |
| **Provenance** | "Last modified" | Git blob hash per quad — every claim traceable |
| **Staleness** | Invisible | `hord status` shows exactly what's out of date |
| **AI integration** | Prompt context | Structured metadata agents can read and validate |

**The core idea:** Hoard separates your files (territory) from metadata about them (map). The map is versioned by git and readable by AI agents. Bad metadata can't corrupt your content. Delete `.hord/` and recompile — everything regenerates.

## How it works

Every piece of metadata is a **quad** — four tab-separated fields:

```
subject     predicate   object      context
c348132e…   v:type      wh:con      a1b2c3d4…
c348132e…   v:bt        9916ba93…   a1b2c3d4…
```

- **subject**: UUID of the entity
- **predicate**: vocabulary term ID (`v:bt` = broader term)
- **object**: UUID of related entity, or a literal value
- **context**: git blob hash of the source file (provenance)

Quads are TSV files in git. Grep them, diff them, cat them. No database required. `hord compile` regenerates them from your org-mode or markdown source files at any time.

Metadata is separated into **overlays** — parallel layers that each answer a different question:

- **Strata** — what is this thing? (type, title, author, WEMI identity)
- **Structural** — how is it organized? (BT, NT, RT, UF, tags)
- **Persona** — what does it mean to me? (role-specific relevance and notes)

Reorganize your hierarchy without touching identity. Switch personas without polluting the shared vocabulary. Each concern has its own layer.

## Build your own hord

```bash
mkdir my-knowledge && cd my-knowledge
git init
hord init --name "my-knowledge"

hord new "Kanban" -t con                          # create a concept card
hord new "Taiichi Ohno" -t per                    # create a person card
hord new                                          # interactive mode
hord capture "A quick thought" -t "idea lean"     # zero-friction capture
hord link add Kanban BT Toyota_Production_System  # typed relation
hord add paper.pdf -k scott:1998seeing            # add a PDF with citekey
hord compile                                      # generate quads
hord status                                       # check for stale metadata
```

Supports both **org-mode** and **markdown**. Import from Obsidian, Logseq, org-roam, Dendron, Notion, or plain markdown:

```bash
hord import ~/Documents/obsidian-vault            # auto-detects source format
```

## Commands

| Command | Purpose |
|---|---|
| `hord init` | Create `.hord/` skeleton in a git repo |
| `hord compile` | Parse org/markdown → generate quads + index |
| `hord query <term>` | Look up entity, show quads + incoming links |
| `hord status` | Show entities with stale metadata |
| `hord new` | Create a new card (interactive or with flags) |
| `hord capture <text>` | Quick-capture a thought with tags and source |
| `hord search <text>` | Full-text search across titles, tags, content |
| `hord tags` | List tag usage, audit definitions |
| `hord link add\|remove\|show\|suggest` | Build and manage thesaurus relations |
| `hord add <file>` | Add a blob (PDF, etc.) to `lib/blob/` with citekey |
| `hord import <path>` | Import from Obsidian, Logseq, org-roam, Dendron, Notion, markdown |
| `hord convert` | Convert between org-mode and markdown |
| `hord export` | Generate browsable static HTML site |
| `hord persona` | Create and manage role-specific overlays |
| `hord mobile serve\|pull` | Mobile capture: HTTP server + inbox processor |
| `hord web` | Local web UI for browsing and creating cards |

## MCP server

Hoard includes an MCP server so Claude (or any MCP-compatible agent) can query, create, and compile cards directly.

```json
{
  "mcpServers": {
    "hoard": {
      "command": "hord-venv/bin/python",
      "args": ["-m", "hord.mcp_server"],
      "env": { "HORD_ROOT": "/path/to/your/hord" }
    }
  }
}
```

9 tools: `query`, `search`, `list_entities`, `status`, `compile`, `vocab_lookup`, `read_content`, `new_card`, `capture`.

## Status

Used daily on a real hord (5,200+ cards, 39,000 quads). Compiles in ~8 seconds.

**Read more:** [Understanding Hoard](docs/INTRODUCTION.md) (five levels of explanation) | [Why Hoard](docs/WHY-HOARD.md) (the full argument) | [Quick Start](docs/QUICKSTART.md) | [Migration Guide](docs/MIGRATION.md) | [All documentation](docs/README.md)

Emacs reader: [hord.el](https://github.com/chenla/hord.el) — card view, live filter, agenda syntax, RT suggestions, blob management.

## License

Code: MIT | Content: CC BY-SA 4.0
