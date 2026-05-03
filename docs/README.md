# Hoard Documentation

## How to read this

Documentation serves four different needs. Start with the one
that matches what you're trying to do.

### I want to understand what Hoard is

- **[Understanding Hoard](INTRODUCTION.md)** — Five levels of
  explanation, from a 30-second pitch to the full architectural
  vision. Start at the level that fits; most people stop at
  level 3.

- **[Why Hoard](WHY-HOARD.md)** — The problem, the library science
  background, and why the design works the way it does. Read this
  if you want the argument, not just the description.

### I want to do something

- **[Quick Start](QUICKSTART.md)** — Install Hoard, run the demo,
  create your first card. Three minutes, no prerequisites beyond
  Python and Git.

- **[Migrating to Hoard](MIGRATION.md)** — AI-assisted walkthrough
  for importing and structuring an existing knowledge base from
  Obsidian, Logseq, org-roam, Notion, or plain markdown.

### I want to look something up

Reference specifications for implementors. These follow RFC 2119
conventions and are designed to be precise enough to build against.

- **[Quad Format](spec-quad-format.md)** — The four-column TSV format
  for metadata assertions.
- **[Directory Conventions](spec-directory-and-types.md)** — Repository
  structure, card types, filename conventions.
- **[Vocabulary](spec-vocabulary.md)** — Controlled vocabulary system,
  term IDs, thesaurus relationships.
- **[Overlays](spec-overlays.md)** — Composable metadata layers: strata,
  structural, persona. Predicate routing and composite views.
- **[MCP Tools](spec-mcp-tools.md)** — Tool contract for AI agent
  integration via the Model Context Protocol.

### I want to understand why a decision was made

Architecture Decision Records (ADRs). Each one covers a single
design choice: what was decided, what alternatives were considered,
and what tradeoffs were accepted.

- **[Territory and Map](design/territory-and-map.md)** — Why metadata
  is separate from content.
- **[Why TSV, Not JSON](design/why-tsv-not-json.md)** — Why quads
  are stored as plain text, not structured formats.
- **[Overlays as Directories](design/overlays-not-branches.md)** — Why
  overlays are directories, not git branches.
- **[E&M as Metadata](design/e-and-m-as-metadata.md)** — Why Expression
  and Manifestation are properties, not containers.
- **[Metadata Is Data](design/metadata-is-data.md)** — Why the system is
  homoiconic: metadata and data are described using the same structures.
- **[Why UUIDs, Not Filenames](design/why-uuids-not-filenames.md)** — Why
  every entity gets a permanent identifier independent of its name.
- **[AI as Essential Collaborator](design/ai-as-collaborator.md)** — Why
  Hoard is designed for AI/agent use first, human use second.
- **[Contextual Scaffolding](design/contextual-scaffolding.md)** — Why
  documentation is card-centric: glossary cards bear the reference weight,
  narrative documents bear the argumentative weight.
- **[WEMI for Concepts](design/wemi-for-concepts.md)** — Why every entity
  has WEMI structure: canonical definition is one Expression, project-specific
  usage is another, persona annotations are Expression-level metadata.

### Glossary

Core concepts are defined as cards in the hord itself. Each card
has a definition, examples, provenance, and relations to other
concepts. When documentation references a term like "quad" or
"overlay," the authoritative definition lives in the corresponding
card — not inline in the document.

Key glossary cards: Quad, Overlay, Controlled Vocabulary, Predicate
Routing, Territory and Map, WEMI, Citekey.

Run `hord query Quad` or `hord query WEMI` to read them, or browse
via `hord web`.
