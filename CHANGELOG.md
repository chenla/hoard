# Changelog

All notable changes to Hoard will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Overlay support**: quads now route to `.hord/overlays/strata/quads/` and
  `.hord/overlays/structural/quads/` based on predicate namespace; views
  compose across overlays at query time — no merge needed; backwards
  compatible with legacy `.hord/quads/` layout
- **`hord capture`** command and MCP `capture` tool: zero-friction quick
  capture of thoughts, notes, observations; creates `wh:cap` card in
  `capture/` and compiles to quads immediately; supports tags (`-t`),
  source context (`-s`), stdin piping (`--stdin`), custom title
- **Formal tagging system**: `v:tag` predicate emitted from `:TAGS:` property
  (org) or `tags:` frontmatter (md); tags are free-form by default, formalized
  by creating `wh:tag` cards (suffix `--15`) with Notes and Processing sections
- **`hord tags`** command: list tag usage across the hord with counts;
  audit which tags have `wh:tag` definitions; `--undefined` filter
- **Format config**: `hord init --format md|org` sets default card format
  in `config.toml`; `hord new` and MCP `new_card` read the config;
  `--format` flag overrides for one-offs
- Four implementor-facing specs in `docs/` (markdown + org-mode):
  quad format, directory conventions and card types, vocabulary system,
  MCP tool contract
- `wh:cap` capture card type (suffix `--14`): quick notes, observations, fleeting
  thoughts; defaults to `capture/` directory; includes `SOURCE` property
- Strata overlay: compiler recognizes WO, EO, MO, IO relations in card files,
  emits `v:s-wo`, `v:s-eo`, `v:s-mo`, `v:s-io` quads; query displays WEMI
  relationships in a separate section from structural relationships
- `hord new` command: create cards with auto-generated UUID, timestamp, and
  type scaffold; supports org-mode and markdown; type shortcuts (`-t con`,
  `-t per`, `-t wrk`); `--edit` flag to open in $EDITOR
- `new_card` MCP tool: AI agents can create cards directly
- Three example Strata cards in TPS hord: book as Whole, Japanese original
  and English translation as Expressions
- `v:author` predicate: extract and compile author metadata from card files
- `bib-import.py` script: generate work cards from cited BibTeX entries
- `hord export` command: generates a browsable static HTML site from a hord;
  one page per entity with clickable links, Strata section, incoming links,
  notes; index page grouped by entity type; self-contained (inline CSS, no
  external dependencies)
- MCP server now exposes 9 tools (added `capture`, `new_card`)
- README: pipx install instructions, cloud brain comparison table,
  MCP server setup, capture examples
- **`hord import`** command: import notes from Obsidian, Logseq, org-roam,
  Dendron, Notion, or plain markdown; auto-detects source format; two-pass
  link resolution (wikilinks → UUID); `--dry-run` for preview
- **`hord add`** command: add files (PDF, EPUB, etc.) to `lib/blob/` with
  citekey-based naming (`author:yearslug.ext`); creates `wh:wrk` card with
  `:CITEKEY:` and `:NOTER_DOCUMENT:` properties; `--context` generates LOD
  summary file; detects existing cards by citekey; `--link` attaches blob
  to existing card
- **`hord link`** command group: interactive thesaurus building
  - `hord link add` — create typed relations (BT/NT/RT/TT/UF/PT etc.)
    between cards with automatic reciprocal links
  - `hord link remove` — remove relations (and reciprocals)
  - `hord link show` — display all outgoing and incoming relations for a card
  - `hord link suggest` — find unlinked related cards by shared tags, types,
    and title word overlap
- **`hord mobile`** command group: mobile capture with hybrid architecture
  - `hord mobile serve` — HTTP capture server with web form, JSON API, and
    optional auth token; `--scratch` mode appends to daily scratch file
  - `hord mobile pull` — process GitHub inbox directory; reads `.md`/`.txt`/`.org`
    files, creates capture cards, archives processed files; `--git-pull` flag
    for cron use
  - `hord mobile setup` — prints setup instructions for HTTP Shortcuts app,
    GitHub inbox, and hybrid configuration
- **`hord web`** command: local web interface for browsing and creating cards
  without Emacs; card list with filter, card detail with relations and notes,
  new card form with type dropdown, quick capture
- **`hord new` interactive mode**: when called without arguments, prompts for
  title, type (numbered menu of all 16 types), source, and task-specific fields
- Three new docs:
  - `docs/INTRODUCTION.md` — five-level LOD explanation (elevator pitch through
    deep architectural vision)
  - `docs/MIGRATION.md` — AI-assisted migration walkthrough (phased: import,
    classify, link, blob, verify)
  - `docs/spec-overlays.md` — overlay architecture specification (strata,
    structural, persona, flow-deferred, predicate routing, composite views)

### Fixed
- Vocabulary files (terms.tsv, relations.tsv) now ship as package data inside
  the `hord` package; `hord init` works correctly from pipx/pip installs, not
  just development checkouts

## [0.1.0] - 2026-04-10

Initial proof of concept. Semantic metadata overlays for git repositories.

### Added
- `.hord/` directory structure with UUID-sharded quad store
- TSV quad format: subject, predicate, object, context (blob hash)
- Option C addressing: UUID for identity, git blob hash for provenance
- Controlled vocabulary system (`vocab/terms.tsv`, `vocab/relations.tsv`)
  - `v:` namespace: metadata predicates (BT, NT, RT, UF, USE, TT, PT, TYPE, TITLE)
  - `v:s-` namespace: Strata predicates (WEMI relationships)
  - `wh:` namespace: word-hord entity types (Concept, Person, Work, Place, etc.)
- CLI commands:
  - `hord init` — create `.hord/` skeleton in a git repo
  - `hord compile` — parse org/markdown files into quads + index
  - `hord query` — look up entity by name/UUID, show quads + incoming links
  - `hord status` — detect stale metadata (blob hash mismatch)
  - `hord convert` — bidirectional conversion between org-mode and markdown
- Org-mode parser: property drawers, relations sections, type inference
- Markdown parser: YAML frontmatter, relations lists, aliases
- MCP server (`python -m hord.mcp_server`) with 7 tools:
  - `query`, `search`, `list_entities`, `status`, `compile`, `vocab_lookup`, `read_content`
- TPS example hord: 21 records (Toyota Production System domain), dual org + markdown
- WHY-HOARD positioning paper
- Architecture documentation (four overlay types)
