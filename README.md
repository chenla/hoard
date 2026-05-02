# Hoard

**Semantic metadata overlays for git repositories.**

Hoard adds a `.hord/` directory to any git repo — structured metadata (quads, controlled vocabulary, identity) that sits alongside your content. Think `.git/` but for knowledge structure.

## Why not a flat wiki?

Systems like Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) store knowledge as markdown files with inline links. That works until it doesn't:

| | Flat Wiki | Hoard |
|---|---|---|
| **Identity** | Filenames (break on rename) | UUIDs (stable forever) |
| **Relationships** | Inline `[[links]]` (fragile, untyped) | Quad store with typed predicates (`BT`, `NT`, `RT`) |
| **Vocabulary** | Ad hoc tags, AI picks whatever word | Formal thesaurus (`BT`/`NT`/`RT`/`UF`/`USE`) |
| **Multilingual** | Separate pages per language | `UF` maps equivalent terms: Kaizen = 改善 = continuous improvement |
| **Provenance** | "Last modified" timestamp | Git blob hash per quad — every claim traceable to a file version |
| **Staleness** | Invisible — confident prose that's quietly wrong | `hord status` shows exactly what's out of date |
| **AI integration** | Prompt context (unstructured) | Structured metadata agents can read, write, and validate |

**The core idea:** Hoard separates *territory* (your files) from *map* (the metadata about them). The map is version-controlled, vocabulary-controlled, and agent-friendly. A flat wiki gives you one view; Hoard gives you as many views as you need.

## Why not a cloud brain?

Tools like Open Brain and similar AI-capture systems store thoughts in cloud databases with embeddings. Hoard captures the same way but keeps everything local and structured:

| | Cloud Brain (e.g. Open Brain) | Hoard Capture |
|---|---|---|
| **Storage** | Cloud database (Supabase, etc.) | Git repo — local, yours |
| **Format** | JSON rows in Postgres | Org-mode or Markdown files |
| **Metadata** | Auto-extracted by AI | Tags + source, user-controlled |
| **Queryable** | Semantic search (embeddings) | Quad store + `hord query` / `hord tags` |
| **Structured** | Flat key-value | Typed cards with overlay separation (Strata, Structural) |
| **Portable** | Locked to cloud instance | `git clone` and done |
| **AI access** | MCP → cloud API | MCP → local files |

```bash
# Quick capture — same velocity, structured output
hord capture "Kanban is a pull system" -t "tps lean"
hord capture "Interesting paper on X" -s reading -t research
echo "Long note..." | hord capture --stdin -t notes
```

**Read more:** [Understanding Hoard](docs/INTRODUCTION.md) (five levels of explanation) | [Why Hoard](docs/WHY-HOARD.md) (the full argument) | [Quick Start](docs/QUICKSTART.md) (install to first query) | [Migration Guide](docs/MIGRATION.md) (import from other tools) | [All documentation](docs/README.md)

## Install

```bash
# Option 1: pipx (recommended — installs in isolated venv)
pipx install hoard-git

# Option 2: pip in a venv
python3 -m venv .venv && source .venv/bin/activate
pip install hoard-git
```

Don't have pipx? `sudo apt install pipx` (Debian/Ubuntu) or `pip install pipx`.

## Quick start

```bash
git clone https://github.com/chenla/hoard
cd hoard/examples/tps-hord
hord query Toyota_Production_System--4
```

Output:

```
════════════════════════════════════════════════════════════
  Toyota Production System—4
  c348132e-7cdf-438d-9a1f-69d75f382bee
════════════════════════════════════════════════════════════

          TYPE  wh:con
            TT  Concept—8  (852a6e49…)
            BT  Lean Manufacturing—4  (9916ba93…)
            NT  Kanban—4  (d4e5f6a7…)
            NT  Jidoka—4  (d4e5f6a7…)
            NT  Just-in-Time Manufacturing—4  (d4e5f6a7…)
            NT  Kaizen—4  (d4e5f6a7…)
            NT  Muda—4  (d4e5f6a7…)
            RT  Andon—4  (d4e5f6a7…)
            RT  Poka-yoke—4  (d4e5f6a7…)
            RT  Heijunka—4  (d4e5f6a7…)
            RT  Genchi Genbutsu—4  (d4e5f6a7…)
            UF  TPS
            PT  Toyota Production System—4

────────────────────────────────────────────────────────────
  Incoming links:

  Taiichi Ohno—7  (e5f6a7b8…)
    ← RT
  Shigeo Shingo—7  (e5f6a7b8…)
    ← RT
  W. Edwards Deming—7  (e5f6a7b8…)
    ← RT
  ...
```

That's one query showing: 5 sub-concepts, 4 related concepts, an alias, and 14 incoming links from people, books, and related concepts — all resolved from structured quads, not scraped from prose.

## Build your own hord

```bash
mkdir my-knowledge && cd my-knowledge
git init
hord init --name "my-knowledge"
# Add org-mode or markdown files to content/
hord compile content/
hord query <filename-or-uuid>
hord status
```

Hoard supports both **org-mode** and **markdown** content files. Use whichever you prefer — both produce identical quads.

### Markdown format

Markdown records use YAML frontmatter for metadata:

```markdown
---
id: c348132e-7cdf-438d-9a1f-69d75f382bee
type: wh:con
title: Kanban—4
created: 2026-04-22T10:00@Hong Kong
license: MIT/CC BY-SA 4.0
relations:
  - "TT: 852a6e49-4b9c-429e-b612-6c505ab78827  # Concept"
  - "BT: c348132e-7cdf-438d-9a1f-69d75f382bee  # Toyota Production System"
aliases:
  - "看板"
  - "Signboard system"
---

# Kanban

Kanban (看板, literally "signboard") is a scheduling system...
```

### Converting between formats

```bash
# Convert org files to markdown
hord convert content/ --to md --output content-md/

# Convert markdown to org
hord convert content-md/ --to org --output content-org/
```

The TPS demo ships with both formats: `content/` (org-mode) and `content-md/` (markdown).

### Importing from other tools

Hoard can import notes from most PKM systems. Source format is auto-detected:

```bash
hord import ~/Documents/obsidian-vault       # auto-detects Obsidian
hord import ~/org-roam/ --from org-roam       # explicit source
hord import ./exported-notion --from notion   # Notion export
hord import ~/notes --dry-run                 # preview without writing
```

Supported: Obsidian, Logseq, org-roam, Dendron, Notion, plain markdown. Wikilinks are resolved to UUID-based links where possible.

### Adding blobs (PDFs, EPUBs, etc.)

Files that aren't cards — PDFs, EPUBs, images, datasets — go into `lib/blob/` with citekey-based filenames:

```bash
hord add paper.pdf -k scott:1998seeing -t "Seeing Like a State" -a "James C. Scott"
hord add book.epub -k braudel:1992civilization --context   # also generate LOD summary
hord add photo.jpg --no-card                                # blob only, no card
```

This creates a `wh:wrk` card with `:CITEKEY:` and `:NOTER_DOCUMENT:` properties, matching the convention used by `cite:key` references in org-mode.

### Building thesaurus relations

The `hord link` command builds the semantic backbone — typed relations between cards:

```bash
hord link add Kanban BT Lean_Manufacturing     # Kanban is narrower than Lean
hord link add Kanban UF "看板"                   # 看板 is an alias for Kanban
hord link show Kanban                           # show all relations
hord link suggest Kanban                        # find unlinked related cards
hord link remove Kanban RT Muda                 # remove a relation
```

Relations are bidirectional by default — adding `BT` from A→B also adds `NT` from B→A.

## How it works

### The `.hord/` directory

```
.hord/
├── config.toml        # hord name and version
├── index.tsv          # path ↔ UUID mapping
├── vocab/
│   ├── terms.tsv      # controlled vocabulary (term ID → label)
│   └── relations.tsv  # relationships between vocab terms
└── quads/
    └── <prefix>/      # sharded by first 4 chars of UUID
        └── <uuid>.tsv # all metadata for one entity
```

### Quads

Every piece of metadata is a quad — four tab-separated fields:

```
subject     predicate   object      context
c348132e…   v:type      wh:con      a1b2c3d4…
c348132e…   v:bt        9916ba93…   a1b2c3d4…
c348132e…   v:nt        d4e5f6a7…   a1b2c3d4…
```

- **subject**: UUID of the entity this quad describes
- **predicate**: vocabulary term ID (not a raw string — `v:bt` not "broader than")
- **object**: UUID of related entity, or a literal value
- **context**: git blob hash of the source file when this quad was generated

Quads are grep-friendly, git-diffable, and machine-readable. No special database required.

### Vocabulary

Predicates are vocabulary term IDs, not strings. This means:

- Rename a label → change one row in `terms.tsv`, quads untouched
- Split a term into subtypes → add new IDs, old quads remain valid
- Map between vocabularies → crosswalk tables with stable anchors on both sides
- Multilingual support → `UF` (Used For) maps equivalent terms across languages

### Provenance

The context column in every quad is the git blob hash of the source file at the time the quad was generated. `hord status` compares these against current blob hashes to show which entities have stale metadata.

## Commands

| Command | Purpose |
|---|---|
| `hord init` | Create `.hord/` skeleton in a git repo |
| `hord compile <path>` | Parse org/markdown files → generate quads + index |
| `hord query <term>` | Look up entity, show quads + incoming links |
| `hord status` | Show entities with stale metadata |
| `hord convert <path> --to md\|org` | Convert between org-mode and markdown |
| `hord new -t <type>` | Create a new card with UUID, timestamp, type scaffold |
| `hord capture <text>` | Quick-capture a thought with tags and source context |
| `hord tags` | List tag usage and audit which tags have definitions |
| `hord export <path>` | Generate browsable static HTML site from a hord |
| `hord import <path>` | Import notes from Obsidian, Logseq, org-roam, Dendron, Notion, or plain markdown |
| `hord add <file>` | Add a blob (PDF, EPUB, etc.) to `lib/blob/` with citekey naming and optional card |
| `hord link add\|remove\|show\|suggest` | Build and manage thesaurus relations between cards |
| `hord mobile serve\|pull\|setup` | Mobile capture: HTTP server + GitHub inbox processor |
| `hord web` | Local web interface for browsing and creating cards (no Emacs needed) |

## The demo dataset

The `examples/tps-hord/` directory contains 21 records about the Toyota Production System in both org-mode (`content/`) and markdown (`content-md/`) formats — concepts (Kanban, Jidoka, Kaizen, JIT, Muda), people (Taiichi Ohno, Shigeo Shingo, W. Edwards Deming), and bibliographic works. It demonstrates:

- **Identity**: every entity has a UUID, independent of filename
- **Typed relationships**: `BT` (broader), `NT` (narrower), `RT` (related) — not just "links"
- **Cross-type links**: people → concepts → books, all traversable
- **Multilingual aliases**: Kanban = 看板, Kaizen = 改善, Jidoka = 自働化
- **Provenance**: every quad traceable to a specific file version
- **Staleness detection**: modify any file, `hord status` flags it immediately

## Architecture

Hoard is built on three principles from library science and knowledge engineering:

1. **Territory vs. Map.** Your files are the territory. Hoard metadata is the map. The map never modifies the territory. Bad metadata can't corrupt your content.

2. **Controlled vocabulary.** Every predicate is a term ID in a vocabulary you own. No magic strings. No implicit semantics. The vocabulary is explicit, versionable, and shareable.

3. **AI as collaborator.** Hoard is designed for AI/agent use first, human use second. The structured metadata is what makes AI agents effective — they can read, validate, and extend the knowledge graph without hallucinating structure.

## Status

Dogfooding — used daily for real knowledge work. Preparing for alpha release.

- Org-mode and markdown content files (both produce identical quads)
- Format conversion between org and markdown (`hord convert`)
- Card creation with type scaffolding (`hord new`)
- Static HTML export (`hord export`)
- MCP server for AI agent integration (9 tools)
- Import from Obsidian, Logseq, org-roam, Dendron, Notion, or plain markdown (`hord import`)
- Blob management with citekey naming and LOD context files (`hord add`)
- Interactive thesaurus building with reciprocal links and suggestions (`hord link`)
- Emacs reader ([hord.el](https://github.com/chenla/hord.el)) with card view, live filter, RT suggestions, blob add, and link management
- Single-branch metadata (overlay branches deferred — predicates already self-identify)

## MCP server (AI agent integration)

Hoard includes an MCP server so Claude (or any MCP-compatible agent) can query, create, and compile cards directly.

If you installed with pipx:

```json
{
  "mcpServers": {
    "hoard": {
      "command": "~/.local/pipx/venvs/hoard-git/bin/python",
      "args": ["-m", "hord.mcp_server"],
      "env": {
        "HORD_ROOT": "/path/to/your/hord"
      }
    }
  }
}
```

Add this to `~/.claude/settings.json` (Claude Code) or your MCP client config. The server exposes 9 tools: `query`, `search`, `list_entities`, `status`, `compile`, `vocab_lookup`, `read_content`, `new_card`, and `capture`.

## License

Code: MIT | Content: CC BY-SA 4.0
