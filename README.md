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

## Quick start

```bash
git clone https://github.com/deerpig/hoard
cd hoard
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Explore the demo
cd examples/tps-hord
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
# Add org-mode files to content/
hord compile content/
hord query <filename-or-uuid>
hord status
```

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
| `hord compile <path>` | Parse org files → generate quads + index |
| `hord query <term>` | Look up entity, show quads + incoming links |
| `hord status` | Show entities with stale metadata |

## The demo dataset

The `examples/tps-hord/` directory contains 21 org-mode records about the Toyota Production System — concepts (Kanban, Jidoka, Kaizen, JIT, Muda), people (Taiichi Ohno, Shigeo Shingo, W. Edwards Deming), and bibliographic works. It demonstrates:

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

This is v0.1 — a proof of concept. Currently supports:

- Org-mode files as content (both old and new format records)
- Single-branch metadata (overlay branches coming in v0.2)
- Local vocabulary (cross-hord vocabulary sharing coming in v0.3)

## License

MIT
