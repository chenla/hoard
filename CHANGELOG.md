# Changelog

All notable changes to Hoard will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `wh:cap` capture card type (suffix `--14`): quick notes, observations, fleeting
  thoughts; defaults to `capture/` directory (separate from reference cards in
  `content/`); includes `SOURCE` property for context reconstruction (reading,
  conversation, observation, etc.); supported in CLI (`hord new -t cap -s reading`),
  MCP (`new_card` with `source` parameter), and Emacs (`C-c w c`)
- Strata overlay: compiler recognizes WO, EO, MO, IO relations in card files,
  emits `v:s-wo`, `v:s-eo`, `v:s-mo`, `v:s-io` quads; query displays WEMI
  relationships in a separate section from structural relationships
- `hord new` command: create cards with auto-generated UUID, timestamp, and
  type scaffold; supports org-mode and markdown; type shortcuts (`-t con`,
  `-t per`, `-t wrk`); `--edit` flag to open in $EDITOR
- `new_card` MCP tool: AI agents can create cards directly
- Three example Strata cards in TPS hord: book as Whole, Japanese original
  and English translation as Expressions
- `hord export` command: generates a browsable static HTML site from a hord;
  one page per entity with clickable links, Strata section, incoming links,
  notes; index page grouped by entity type; self-contained (inline CSS, no
  external dependencies)

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
