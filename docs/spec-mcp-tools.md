# Hoard MCP Tool Contract

Specification for the Hoard MCP server tool interface. This document
defines the contract between AI agents and a hord, mediated by the
Model Context Protocol.

Version: 0.1 (2026-05-01)

---

## 1. Overview

The Hoard MCP server exposes a hord's knowledge graph to AI agents as
a set of tools over the Model Context Protocol (MCP). Agents can
query entities, search by keyword, read source content, create new
cards, compile metadata, inspect vocabulary, and check freshness --
all through the same functions the CLI uses.

**Primary consumers:** AI agents (Claude, other MCP-capable models).
Human users interact through the `hord` CLI, which calls the same
underlying library code. The MCP server is not a separate API layer;
it is a thin wrapper that exposes the plumbing directly.

**Transport:** stdio only. The server runs as a local subprocess
spawned by the AI agent's host process (e.g., Claude Code).

**Protocol:** MCP (Model Context Protocol) via the `mcp` Python
package's `FastMCP` class. Each tool is registered as an MCP tool
and returns a single string value.


## 2. Setup

### 2.1 Configuration

Add the server to your MCP client configuration. For Claude Code,
edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "hoard": {
      "command": "/path/to/hoard/.venv/bin/python",
      "args": ["-m", "hord.mcp_server"],
      "env": {
        "HORD_ROOT": "/path/to/your/hord"
      }
    }
  }
}
```

### 2.2 Hord Root Resolution

The server resolves the hord root in this order:

1. `HORD_ROOT` environment variable, if set and the path contains a
   `.hord/` directory.
2. Walk up from the current working directory looking for `.hord/`.
3. If neither succeeds, all tool calls fail with:
   `"No hord found. Set HORD_ROOT or run from inside a hord."`

### 2.3 Prerequisites

The hord must be initialized (`hord init`) and compiled at least once
(`hord compile`) before `query`, `search`, `list_entities`, `status`,
or `read_content` will return meaningful results. The `compile` and
`new_card` tools can be used on a freshly initialized hord.

### 2.4 Entry Point

The server can also be invoked as `python -m hord.mcp_serve`, which
delegates to `hord.mcp_server.main()`.


## 3. Tool Reference

All tools return a single `str` value. There are no structured JSON
responses -- output is plain text, sometimes with indentation and
alignment for readability. Every tool call resolves `HORD_ROOT`
independently.

---

### 3.1 `query`

Look up an entity by UUID, filename, or partial UUID. Returns all
quads for the entity with vocabulary labels resolved, plus all
incoming links.

#### Parameters

| Name   | Type  | Required | Description                                      |
|--------|-------|----------|--------------------------------------------------|
| `term` | `str` | yes      | UUID, filename (without extension), relative path, or partial UUID (minimum 4 characters). |

#### Term Resolution

The `term` is matched against the index in this order:

1. Exact match against any index key (path, UUID, or basename).
2. Prefix match: if `term` is at least 4 characters, match any index
   key that starts with it.
3. If no match: returns `"Not found: {term}"`.

#### Return Format

```
Entity: {title or UUID}
UUID: {full UUID}

  {predicate label}: {object value}
  {predicate label}: {resolved title} ({uuid prefix}...)
  ...

Incoming links:
  {source title} ({uuid prefix}...) <- {predicate label}
  ...
```

- The title quad (`v:title`) is displayed in the header and omitted
  from the property list.
- Object values that look like UUIDs (36 chars, 4 hyphens) are
  resolved to their title via `resolve_uuid_label`.
- Predicate IDs are resolved to human-readable labels through the
  vocabulary.
- Incoming links are all quads in the hord where this entity's UUID
  appears as the object.

#### Error Cases

- `"Not found: {term}"` -- no index entry matches.

#### Example

```
Entity: Kanban
UUID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

  Type: Concept
  Broader Term (generic): Lean Manufacturing (f9e8d7c6...)
  Related Term: Pull System (12345678...)

Incoming links:
  Toyota Production System (abcdef12...) <- Related Term
```

---

### 3.2 `search`

Search for entities by name or keyword. Case-insensitive substring
match against index keys (paths, basenames).

#### Parameters

| Name   | Type  | Required | Description                       |
|--------|-------|----------|-----------------------------------|
| `text` | `str` | yes      | Search string (case-insensitive). |

#### Return Format

On match:
```
Found {N} entities:
  {title}  [{type label}]  {UUID}
  {title}  [{type label}]  {UUID}
  ...
```

On no match:
```
No entities matching '{text}'
```

Each result line is indented with two spaces. The type label is
resolved through the vocabulary (e.g., `wh:con` becomes `Concept`).

#### Deduplication

Results are deduplicated by UUID. If multiple index keys match the
same entity, it appears once.

#### Error Cases

- `"No entities matching '{text}'"` -- no index key contains the
  search string.

---

### 3.3 `list_entities`

List all entities in the hord, optionally filtered by type.

#### Parameters

| Name          | Type  | Required | Default | Description                                              |
|---------------|-------|----------|---------|----------------------------------------------------------|
| `entity_type` | `str` | no       | `""`    | Filter by type: vocab ID (`wh:con`) or label (`Concept`). Case-insensitive substring match. |

#### Return Format

```
{N} entities:
  {title}  [{type label}]  {UUID}
  {title}  [{type label}]  {UUID}
  ...
```

Results are sorted alphabetically. Only path-based index entries are
listed (avoids duplicate entries from name-based index keys).

#### Type Filtering

The `entity_type` parameter is matched as a case-insensitive
substring against both the raw vocab ID (e.g., `wh:con`) and the
resolved label (e.g., `Concept`). Passing `"per"` matches `wh:per`
and `Person`.

#### Error Cases

None -- an empty hord returns `"0 entities:\n"`.

---

### 3.4 `status`

Check which entities have stale metadata by comparing git blob hashes.

#### Parameters

None.

#### Return Format

When everything is fresh:
```
All {N} entities are fresh.
```

When stale or missing entities exist:
```
Stale ({N}):
  x {path} (content changed)
  x {path} (no quads)
Missing ({N}):
  ? {path}

{fresh count} fresh, {stale count} stale, {missing count} missing.
```

#### How Freshness Works

Each quad file stores the git blob hash of the source file at compile
time in the `context` field (the fourth column of every quad). The
`status` tool recomputes the blob hash of each source file and
compares it to the stored hash. If they differ, the entity is stale
and needs recompilation.

#### Error Cases

- `"No index found. Run 'hord compile' first."` -- no
  `.hord/index.tsv` exists.

---

### 3.5 `compile`

Compile org-mode and markdown files into Hoard quads. This is a
**write operation** that modifies `.hord/` contents.

#### Parameters

| Name   | Type  | Required | Default | Description                                         |
|--------|-------|----------|---------|-----------------------------------------------------|
| `path` | `str` | no       | `"."`   | Relative path within hord, or absolute path. If a file, compiles that file only. If a directory, scans recursively. |

#### What Compile Does

1. Scans the path for `.org` and `.md` files.
2. Parses each file, extracting UUID, type, title, relations, and
   aliases from the file's metadata block.
3. Converts relations to quads using the `REL_TO_PREDICATE` mapping:

   | Relation | Predicate   | Meaning                   |
   |----------|-------------|---------------------------|
   | TT       | `v:tt`      | Top Term                  |
   | PT       | `v:pt`      | Preferred Term            |
   | BT       | `v:bt`      | Broader Term              |
   | BTG      | `v:btg`     | Broader Term (generic)    |
   | BTI      | `v:bti`     | Broader Term (instance)   |
   | BTP      | `v:btp`     | Broader Term (partitive)  |
   | NT       | `v:nt`      | Narrower Term             |
   | NTG      | `v:ntg`     | Narrower Term (generic)   |
   | NTI      | `v:nti`     | Narrower Term (instance)  |
   | NTP      | `v:ntp`     | Narrower Term (partitive) |
   | RT       | `v:rt`      | Related Term              |
   | UF       | `v:uf`      | Used For (non-preferred)  |
   | USE      | `v:use`     | Use (preferred form)      |
   | WO       | `v:s-wo`    | Work Of (Strata)          |
   | EO       | `v:s-eo`    | Expression Of (Strata)    |
   | MO       | `v:s-mo`    | Manifestation Of (Strata) |
   | IO       | `v:s-io`    | Instance Of (Strata)      |

4. Computes the git blob hash of each source file and stores it as
   the context (fourth field) of every quad.
5. Writes quad files to `.hord/quads/{uuid[:4]}/{uuid}.tsv`.
6. Overwrites `.hord/index.tsv` with path-to-UUID mappings.

#### Return Format

```
Compiled {N} files -> {M} quads, {K} index entries.
```

#### Error Cases

- `"Path does not exist: {path}"` -- the resolved path does not exist.
- `"No valid records found."` -- no files with valid metadata found.

---

### 3.6 `vocab_lookup`

Look up vocabulary terms by ID or keyword, or list all terms.

#### Parameters

| Name   | Type  | Required | Default | Description                                         |
|--------|-------|----------|---------|-----------------------------------------------------|
| `term` | `str` | no       | `""`    | Term ID (`v:bt`), keyword, or empty to list all.    |

#### Return Format

**All terms** (no argument):
```
Vocabulary terms:
  {id:<16}  {label:<20}  {scope note}
  ...
```

**Exact match** (term ID found):
```
{id}
  Label: {label}
  Scope: {scope note}
```

**Keyword search** (substring match against ID, label, or scope note):
```
Found {N} terms:
  {id:<16}  {label:<20}  {scope note}
  ...
```

#### Column Alignment

In list mode, the ID field is left-padded to 16 characters and the
label to 20 characters to produce aligned columns.

#### Error Cases

- `"No vocabulary found."` -- no `terms.tsv` in `.hord/vocab/`.
- `"No vocabulary terms matching '{term}'"` -- no matches.

---

### 3.7 `read_content`

Read the full source content of an entity's file (org-mode or
markdown).

#### Parameters

| Name   | Type  | Required | Description                                      |
|--------|-------|----------|--------------------------------------------------|
| `term` | `str` | yes      | UUID, filename, or partial UUID (min 4 chars).   |

#### Term Resolution

Same resolution logic as `query` (exact match, then prefix match).

#### Return Format

The raw file content as a single string. No processing, no metadata
extraction -- the complete file as stored on disk.

#### Error Cases

- `"Not found: {term}"` -- no index entry matches.
- `"Source file not found for {uuid}"` -- index entry exists but the
  file is missing from disk.

---

### 3.8 `new_card`

Create a new card with a UUID and metadata scaffold. This is a
**write operation** that creates a new file in the hord.

#### Parameters

| Name          | Type  | Required | Default     | Description                                                      |
|---------------|-------|----------|-------------|------------------------------------------------------------------|
| `title`       | `str` | yes      | --          | Display name for the card (e.g., "Kanban", "Taiichi Ohno").      |
| `entity_type` | `str` | no       | `"con"`     | Type shortcut or vocab ID. See type table below.                 |
| `fmt`         | `str` | no       | `"org"`     | File format: `"org"` or `"md"`.                                  |
| `content_dir` | `str` | no       | `"content"` | Subdirectory within hord for the new file. Capture cards (`wh:cap`) default to `"capture"` instead. |
| `source`      | `str` | no       | `""`        | Source context for capture cards (e.g., "reading", "conversation", "observation"). |

#### Entity Type Shortcuts

| Shortcut       | Vocab ID  | Filename Suffix |
|----------------|-----------|-----------------|
| `con`, `concept`       | `wh:con`  | `4`             |
| `pat`, `pattern`       | `wh:pat`  | `3`             |
| `key`, `keystone`      | `wh:key`  | `5`             |
| `wrk`, `work`          | `wh:wrk`  | `6`             |
| `per`, `person`        | `wh:per`  | `7`             |
| `cat`, `category`      | `wh:cat`  | `8`             |
| `sys`, `system`        | `wh:sys`  | `9`             |
| `pla`, `place`         | `wh:pla`  | `10`            |
| `evt`, `event`         | `wh:evt`  | `11`            |
| `obj`, `object`        | `wh:obj`  | `12`            |
| `org`, `organization`  | `wh:org`  | `13`            |
| `cap`, `capture`       | `wh:cap`  | `14`            |

Full vocab IDs (e.g., `wh:con`) are also accepted directly.

#### Filename Generation

The filename is constructed as `{slug}--{suffix}.{ext}` where:

- `slug` is the title converted to ASCII, spaces replaced with
  underscores, non-alphanumeric characters stripped.
- `suffix` is the numeric type suffix from the table above.
- `ext` is `org` or `md`.

Example: `new_card(title="Taiichi Ohno", entity_type="per")` creates
`Taiichi_Ohno--7.org`.

#### Return Format

```
Created {relative path}
  UUID: {uuid}
  Type: {vocab ID}
```

#### Error Cases

- `"Unknown type '{entity_type}'. Valid: cap, cat, con, ..."` --
  unrecognized type shortcut.
- `"File already exists: {filepath}"` -- a file with the generated
  name already exists.


## 4. Data Format Contract

### 4.1 Quads

The fundamental data unit is a **quad** -- a four-column TSV record:

```
subject<TAB>predicate<TAB>object<TAB>context
```

| Field     | Content                                                   |
|-----------|-----------------------------------------------------------|
| subject   | UUID of the entity this quad describes.                   |
| predicate | Vocabulary term ID (e.g., `v:type`, `v:bt`, `v:title`).  |
| object    | Value: a literal string, a vocab term ID, or a target UUID. |
| context   | Git blob hash of the source file at compile time.         |

Quad files are stored at `.hord/quads/{uuid[:4]}/{uuid}.tsv`, sharded
by the first four characters of the UUID. Each file has a header line
(`subject\tpredicate\tobject\tcontext`) followed by data lines.

### 4.2 Index

The index at `.hord/index.tsv` maps source file paths to UUIDs:

```
path<TAB>uuid
content/kanban--4.org<TAB>a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

At load time, the index is expanded into a dictionary keyed by:
- The relative file path.
- The UUID itself.
- The filename without extension (basename).

This allows `query` and `read_content` to accept any of these forms.

### 4.3 Vocabulary

Vocabulary terms live in `.hord/vocab/terms.tsv`:

```
id<TAB>label<TAB>scope_note
v:bt<TAB>Broader Term<TAB>Links a concept to a more general concept.
```

Terms use a namespace prefix (`v:` for core vocabulary, `wh:` for
Hoard entity types).

### 4.4 Tool Output Style

All tools return plain text strings. There is no JSON encoding. The
rationale: LLM agents parse natural-language-adjacent text natively,
and plain text is easier to debug via logs. Structured data (quad
files, index, vocabulary) lives on disk in TSV; the MCP tools render
it into readable form.

Key conventions in tool output:
- Indentation uses two spaces for property/result lines.
- UUID references are truncated to 8 characters with an ellipsis
  (`a1b2c3d4...`) when displayed alongside a resolved title.
- Type labels appear in square brackets: `[Concept]`, `[Person]`.
- Error messages start with the error condition, not a prefix like
  "Error:".


## 5. Design Principles

### 5.1 AI-First

The MCP server is designed for AI agents as first-class consumers.
Agents should be able to:

- **Discover** what a hord contains (`list_entities`, `search`).
- **Read** entity metadata and source content (`query`,
  `read_content`).
- **Write** new entities and recompile metadata (`new_card`,
  `compile`).
- **Validate** freshness and consistency (`status`, `vocab_lookup`).

The tool names and parameters are chosen for clarity in tool-use
contexts, not for shell ergonomics.

### 5.2 Plumbing, Not Porcelain

MCP tools call the same library functions as the CLI. There is no
separate "API layer" with its own logic. `compile` in the MCP server
calls the same `parse_org_file`, `write_quads`, and `blob_hash`
functions as `hord compile` on the command line. This means:

- Behavior is identical regardless of entry point.
- Bug fixes apply everywhere.
- The MCP server is a thin wrapper, not a separate codebase.

### 5.3 Text Over JSON

Tool return values are plain text, not JSON. This is a deliberate
choice:

- LLMs process natural text more reliably than nested JSON.
- Debugging is easier -- you can read tool output in logs.
- The structured data (TSV quads, index, vocabulary) is on disk; the
  tools render it for consumption.

If a future consumer needs machine-parseable output, the correct path
is to read the TSV files directly, not to add JSON serialization to
the MCP tools.

### 5.4 Stateless Tools

Every tool call resolves `HORD_ROOT` and loads the index fresh. There
is no session state, no caching, no connection lifecycle. This makes
the server safe to restart, safe to run concurrently with CLI
operations, and trivial to reason about.

### 5.5 Write Operations Are Explicit

Only two tools modify the hord: `compile` (writes quads and index)
and `new_card` (creates a source file). Both are clearly documented
as write operations. Read-only tools never modify any file.
