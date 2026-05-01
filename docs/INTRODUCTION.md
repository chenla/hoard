# Understanding Hoard

*This document explains Hoard at five levels of detail. Start at
the level that fits your needs. Most people never need to go past
level 3.*

---

## Level 1: The Elevator Pitch (30 seconds)

Hoard is **Git for knowledge structure.**

You already use Git to track changes in files. Hoard adds a metadata
layer on top: structured relationships, controlled vocabulary,
stable identifiers. Your notes become queryable, portable, and
AI-readable — without leaving the file formats you already use.

Install it. Run `hord init` in any git repo. Your org-mode or
markdown files get a semantic layer that grows with your knowledge.

---

## Level 2: The Quick Start (5 minutes)

### What it does

Hoard adds a `.hord/` directory to a git repo — think `.git/` but for
knowledge structure. Inside are quads (structured metadata assertions),
a controlled vocabulary, and an index. Outside, your content stays in
org-mode or markdown files, untouched.

### Try it now

```bash
pipx install hoard-git
git clone https://github.com/chenla/hoard
cd hoard/examples/tps-hord

hord query Kanban                    # see a card's relationships
hord search "production"             # search by keyword
hord tags                            # see what's tagged
hord capture "A thought" -t "demo"   # quick capture
hord web                             # browse in your browser
```

### The daily workflow

```bash
hord new "Some Topic" -t con         # create a card
hord capture "Quick idea" -t tags    # capture a thought
hord link add TopicA RT TopicB       # relate two cards
hord add paper.pdf -k author:2026x   # add a reference file
hord compile                         # regenerate metadata
```

That's the entire surface area for daily use. Everything else is
for building, migrating, or extending.

---

## Level 3: The Comparison (10 minutes)

### Why not a flat wiki?

Tools like Karpathy's LLM Wiki store knowledge as markdown files
with inline links. Hoard separates content from structure:

| | Flat Wiki | Hoard |
|---|---|---|
| **Identity** | Filenames (break on rename) | UUIDs (stable forever) |
| **Relationships** | Inline `[[links]]` (untyped) | Typed predicates (BT, NT, RT) |
| **Vocabulary** | Ad hoc tags | Formal thesaurus with equivalence mappings |
| **Multilingual** | Separate pages per language | UF maps equivalent terms across languages |
| **Provenance** | "Last modified" | Git blob hash per quad — every claim traceable |
| **Staleness** | Invisible | `hord status` shows exactly what's out of date |
| **AI integration** | Prompt context | Structured metadata agents can read and validate |

**The core idea:** The map is not the territory. Hoard keeps metadata
separate from content so that a bad map can never corrupt your files,
and you can have as many maps as you need over the same territory.

### Why not a cloud brain?

Tools like Open Brain, NotebookLM, and Mem store thoughts in cloud
databases. Hoard captures the same way but keeps everything local:

| | Cloud Brain | Hoard |
|---|---|---|
| **Storage** | Cloud database | Git repo — local, yours |
| **Format** | JSON/Postgres | Org-mode or Markdown files |
| **Portability** | Locked to provider | `git clone` and done |
| **AI access** | Provider API | MCP server → local files |
| **Structure** | Flat or auto-tagged | Typed cards with overlays |

### Why not Obsidian / Logseq / org-roam?

These are good tools. Hoard doesn't replace them — it structures what
they produce. You can import from any of them (`hord import`) and get
something they don't provide: a queryable, vocabulary-controlled,
overlay-separated metadata layer.

The difference is architectural. Obsidian stores knowledge as linked
markdown. Hoard stores knowledge as *structured assertions about*
linked markdown (or org). When an AI reads your Obsidian vault, it
has to parse prose and guess at structure. When it reads your hord,
the structure is explicit.

---

## Level 4: The Architecture (30 minutes)

### Quads

Every piece of metadata is a quad — four tab-separated fields:

```
subject     predicate   object      context
c348132e…   v:type      wh:con      a1b2c3d4…
c348132e…   v:bt        9916ba93…   a1b2c3d4…
```

- **Subject:** UUID of the entity
- **Predicate:** vocabulary term ID (not a raw string)
- **Object:** UUID of related entity, or a literal value
- **Context:** git blob hash of the source file (provenance)

Quads are grep-friendly, git-diffable, and machine-readable. No
database required. They are derived data — delete them all and
`hord compile` regenerates them from your content files.

### Controlled Vocabulary

Predicates are vocabulary term IDs, not strings. The vocabulary
lives in `.hord/vocab/terms.tsv`:

```
v:bt    Broader Term
v:nt    Narrower Term
v:rt    Related Term
v:uf    Used For
```

This means:
- Rename a label → change one row, all quads untouched
- Add multilingual labels → UF maps across languages
- Split a term into subtypes → add new IDs, old quads remain valid

The vocabulary system follows ANSI/NISO Z39.19, the international
standard for thesaurus construction that has been in production use
for over fifty years.

### Overlays

Different kinds of metadata answer different questions. Hoard
separates them into overlays:

| Overlay | Question | Predicates |
|---------|----------|------------|
| **Strata** | What is this thing? | type, title, author, status |
| **Structural** | How is it organized? | BT, NT, RT, UF, tags |
| **Persona** | What does it mean to me? | relevance, priority, notes |
| **Flow** (future) | How does change propagate? | (deferred) |

Overlays live in `.hord/overlays/<name>/quads/`. Predicate routing
assigns each quad to its overlay at compile time. Views are composed
at read time by merging from one or more overlays.

**Why this matters:** Reorganizing your hierarchy (structural) never
touches identity (strata). A persona's relevance marks never pollute
the shared vocabulary. Each concern has its own layer.

### Entity Types

Every card has a type drawn from a fixed vocabulary:

| Type | Suffix | What it represents |
|------|--------|-------------------|
| `wh:con` | 4 | Concept |
| `wh:pat` | 3 | Pattern |
| `wh:key` | 5 | Keystone |
| `wh:wrk` | 6 | Work (book, paper, etc.) |
| `wh:per` | 7 | Person |
| `wh:pla` | 10 | Place |
| `wh:org` | 13 | Organization |
| `wh:sys` | 9 | System |
| `wh:cap` | 14 | Capture (quick note) |
| `wh:task` | 18 | Task |
| `wh:tag` | 15 | Tag definition |
| `wh:persona` | 16 | Persona (role) |
| `wh:office` | 17 | Office (transferable title) |

The suffix appears in the filename (`Kanban--4.org`) and the display
title (`Kanban—4`). This is deliberately visible — you can tell a
concept from a person from a work at a glance.

### Provenance

The context column in every quad is the git blob hash of the source
file when the quad was generated. `hord status` compares these
against current blob hashes. If you edit a card and don't recompile,
status shows it as stale. This is how Hoard answers "is this metadata
still accurate?" — a question that flat wikis and cloud brains cannot
answer at all.

---

## Level 5: The Vision (deep dive)

### WEMI and Identity Across Form

Hoard's strata overlay is built on a generalized form of FRBR — the
library science framework for describing works across realizations.
WEMI stands for Whole, Expression, Manifestation, Instance:

- **Whole:** The abstract concept (e.g., "Hamlet")
- **Expression:** A specific realization (Shakespeare's 1603 text)
- **Manifestation:** A specific format (the Penguin Classics edition)
- **Instance:** A specific copy (the one on your shelf)

Most knowledge tools flatten everything to one level. Hoard
preserves the full stack. This matters when the same idea appears
as a paper, a talk, a blog post, and a chapter — they're all
expressions of one whole, and the relationships between them are
structural, not accidental.

### Personas and Offices

A persona is a role you play — researcher, sysadmin, gardener. Each
persona has its own overlay, its own relevance marks, its own view
of the shared knowledge graph. Switch personas and the same hord
looks different.

An office is a role that persists beyond any individual holder.
"Department head" is an office; "Jane, who is currently department
head" is a persona filling that office. This distinction matters
for institutional knowledge — when Jane leaves, the office's
annotations persist and transfer.

### Composable Views

A view is the result of reading from one or more overlays. Views are
ephemeral — computed on demand, never stored. This means:

- A "researcher" view reads strata + structural + persona-researcher
- A "public" view reads strata + structural (no persona data)
- A "compare" view reads two persona overlays side by side
- A "structural-only" view shows hierarchy without identity clutter

Views are the mechanism that makes overlays useful. Without them,
overlays are just directories. With them, overlays become lenses.

### The Context Problem

AI systems are racing to capture context — your preferences,
knowledge, working patterns. But every provider captures context
into their own silo. Switch providers and you lose months of
accumulated context. The switching cost grows over time, creating
vendor lock-in.

Hoard is designed to be the portable, provider-agnostic context
layer. Your hord is a git repo on your machine. Any AI can read it
through MCP. Switch from Claude to GPT to Gemini — your context
stays. The structure is explicit enough that any competent model can
read it without training.

This is not a hypothetical future feature. It works today: configure
the MCP server, point any MCP-compatible agent at your hord, and the
agent can query, create, and extend your knowledge graph.

### Beyond Personal Knowledge

Hoard is designed for personal use but the architecture scales to
institutional knowledge. A corporate hord with role-based persona
overlays. A research group's shared vocabulary with individual
structural overlays. A supply chain's flow overlay connecting
producers, processors, and distributors.

The overlay model means these don't require a centralized system.
Each participant maintains their own hord. Shared vocabulary and
cross-hord federation (future) enable composition without
centralization.

---

## Which Level Do You Need?

- **Trying it out:** Level 2 (Quick Start). Install, run the demo,
  capture a few thoughts.

- **Deciding whether to migrate:** Level 3 (Comparison). Understand
  what Hoard does differently and whether that matters to you.

- **Building tools or integrations:** Level 4 (Architecture). Read
  the quad format, vocabulary, and overlay specs in `docs/`.

- **Understanding the design philosophy:** Level 5 (Vision). Read
  [Why Hoard](WHY-HOARD.md) for the full argument.

- **Migrating your existing notes:** Read [Migrating to Hoard](MIGRATION.md).
