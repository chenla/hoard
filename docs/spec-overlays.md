# Hoard Overlay Specification

**Status:** Working Draft, 2026-05-01
**Audience:** Implementors building tools that read or write hord overlays

---

## 1. Overview

A hord stores metadata about content.  But different kinds of metadata
answer fundamentally different questions.  "What is this thing?" is a
different question from "how is this thing organized?" — and the answer
to each can change independently.

Hoard separates these questions into **overlays**: parallel metadata
layers that each describe the same territory from a different angle.
Overlays are the composable lens model.  A tool reads one overlay, or
several, or all of them — and gets exactly the view it needs.

This specification defines the overlay mechanism, the predefined
overlay types, and the rules for predicate routing.


## 2. Conformance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document
are to be interpreted as described in RFC 2119.

An **overlay** is a named subdirectory of `.hord/overlays/` that
contains its own `quads/` directory using the same UUID-sharded layout
as the legacy `.hord/quads/` directory.


## 3. Directory Layout

```
.hord/
  overlays/
    strata/
      quads/
        <prefix>/
          <uuid>.tsv
    structural/
      quads/
        <prefix>/
          <uuid>.tsv
    persona-researcher/
      quads/
        <prefix>/
          <uuid>.tsv
```

Each overlay directory MUST contain a `quads/` subdirectory.  Quad
files within an overlay follow the same format specified in the Quad
Format Specification — tab-separated, four columns, one assertion per
line.

The `<prefix>` is the first four characters of the entity UUID.  The
file is named `<uuid>.tsv`.  This sharding scheme is identical to the
legacy layout and is specified in the Directory Conventions document.


## 4. Predefined Overlay Types

### 4.1. Strata Overlay

**Question answered:** What is this thing?

The strata overlay holds identity and descriptive metadata — the
assertions that define what an entity *is* across time and form.

**Predicates routed to strata:**

| Predicate    | Meaning                                |
|-------------|----------------------------------------|
| `v:type`     | Entity type (wh:con, wh:per, etc.)    |
| `v:title`    | Display title                          |
| `v:author`   | Creator attribution                    |
| `v:status`   | Task status (todo, done, waiting, etc.)|
| `v:due`      | Due date                               |
| `v:scheduled`| Scheduled date                         |
| `v:s-wo`     | WEMI Whole-level scope note            |
| `v:s-eo`     | WEMI Expression-level scope note       |
| `v:s-mo`     | WEMI Manifestation-level scope note    |
| `v:s-io`     | WEMI Instance-level scope note         |
| `v:s-type`   | WEMI level type                        |

**Design rationale:** Identity is the slowest-changing layer.  A
concept's type, title, and authorship rarely change.  When they do,
the change is significant — it means the entity itself is being
redefined, not just reorganized.  Separating identity metadata means
a reorganization (structural overlay change) never touches identity,
and an identity correction never disrupts organization.

### 4.2. Structural Overlay

**Question answered:** How is this thing organized?

The structural overlay holds thesaurus relationships, tags, and
vocabulary mappings — the assertions that define how entities relate
to each other within a knowledge graph.

**Predicates routed to structural:**

| Predicate | Meaning                          |
|----------|----------------------------------|
| `v:tt`    | Top Term                         |
| `v:pt`    | Preferred Term                   |
| `v:bt`    | Broader Term                     |
| `v:btg`   | Broader Term (generic)           |
| `v:bti`   | Broader Term (instance)          |
| `v:btp`   | Broader Term (partitive)         |
| `v:nt`    | Narrower Term                    |
| `v:ntg`   | Narrower Term (generic)          |
| `v:nti`   | Narrower Term (instance)         |
| `v:ntp`   | Narrower Term (partitive)        |
| `v:rt`    | Related Term                     |
| `v:uf`    | Used For (non-preferred label)   |
| `v:use`   | See (preferred form)             |
| `v:tag`   | Free-form tag                    |

**Design rationale:** Organization changes more often than identity.
You might reclassify a concept from one hierarchy to another, split
a broad category into narrower terms, or add new RT links as your
understanding deepens.  These changes are significant but should not
disturb the strata layer.

### 4.3. Persona Overlays

**Question answered:** What does this thing mean to me in this role?

Persona overlays hold role-specific annotations — relevance marks,
priority ratings, and contextual notes that a specific persona has
attached to entities.  Unlike strata and structural overlays, persona
overlays are user-defined and multiple can coexist.

**Naming convention:** `persona-<name>` (e.g. `persona-researcher`,
`persona-sysadmin`, `persona-gardener`).

**Predicates routed to persona overlays:**

| Predicate      | Meaning                          |
|---------------|----------------------------------|
| `v:p-relevant` | Relevance flag for this persona  |
| `v:p-note`     | Contextual note from this persona|
| `v:p-priority` | Priority rating (1=highest)      |

**Design rationale:** Different roles see the same knowledge graph
differently.  A "researcher" persona might flag a paper as highly
relevant; a "sysadmin" persona might flag a configuration pattern.
Persona overlays allow multiple simultaneous viewpoints without
polluting the shared structural or identity metadata.

### 4.4. Flow Overlay (Deferred)

**Question answered:** How does change propagate through this system?

The flow overlay will describe dynamics: how information, materials,
and energy move through the systems that strata and structural
overlays describe statically.  This overlay is not yet implemented
and is deferred beyond the current release.

**Design constraint:** The current overlay architecture MUST NOT
preclude the future addition of flow overlays.  Specifically:

- The predicate routing mechanism must be extensible to new
  overlay types without changing the existing routing logic.
- The quad format must not assume that predicates are limited
  to the strata/structural/persona types defined above.
- The composite view mechanism (reading from multiple overlays)
  must work with any number of overlays, not just two or three.


## 5. Predicate Routing

When `hord compile` generates quads from source files, each quad is
routed to an overlay based on its predicate:

1. If the predicate is in the strata set → `strata` overlay
2. If the predicate is in the structural set → `structural` overlay
3. If the predicate starts with `v:p-` → persona overlay (named by
   the current persona context, or `structural` as fallback)
4. All other predicates → `structural` overlay (default)

This routing happens at compile time.  The source files are unaware
of overlays — a single org card with `:TYPE:`, `BT ::`, and `RT ::`
relations produces quads that land in both strata and structural
overlays.

**Implementor note:** The predicate routing table is defined in
`hord/quad.py` as `STRATA_PREDICATES` and `STRUCTURAL_PREDICATES`.
Adding a new predicate requires adding it to the appropriate set.
Unknown predicates default to structural — this is intentional.  A
tool that writes a custom predicate should not need to modify the
routing table to function; it will just land in the structural
overlay by default.


## 6. Composite Views

Reading from a hord means composing a view from one or more overlays.
The query engine reads quad files from each requested overlay and
merges the results.

**Rules for composition:**

- **All overlays** (default): `hord query` and MCP tools read from
  all overlays.  The result is the union of all quads for the
  requested entity.

- **Single overlay**: A tool MAY request quads from only one overlay
  (e.g., "show me only structural relationships").  This is useful
  for tools that operate on one concern at a time.

- **Overlay precedence**: When the same predicate appears in multiple
  overlays for the same entity (which should not normally happen
  given correct routing), the implementation reads them all.  There
  is no precedence — duplicates are visible to the consumer.

- **Legacy compatibility**: If no overlays exist (no `.hord/overlays/`
  directory), the implementation falls back to reading from
  `.hord/quads/` directly.  This ensures hords created before
  overlay support was added continue to work.


## 7. Creating Overlays

Overlays are created automatically by `hord compile` when it routes
quads.  The compiler creates the overlay directory structure on demand.

Overlays MAY also be created manually:

```bash
mkdir -p .hord/overlays/persona-researcher/quads
```

There is no registration step.  An overlay exists when its directory
exists and contains a `quads/` subdirectory.

Persona overlays are created via the `hord persona create` command,
which creates both the overlay directory and a persona card in
`content/`.


## 8. Relationship to Git Branches

The current implementation stores overlays as directories within a
single branch.  The original design envisioned overlays as separate
git branches that are never merged — each branch holding a different
metadata map of the same territory.

**Current approach:** Directories within a single branch, composed at
read time.  This is simpler, avoids branch management overhead, and
works well for the strata/structural/persona split where overlays are
non-overlapping by predicate routing.

**Future possibility:** The git branch approach may be revisited for
scenarios where overlays need independent version histories — for
example, a corporate hord where the structural overlay is maintained
by a team and the strata overlay is maintained by a librarian.  The
current directory-based approach does not preclude this migration.

**Implementor guidance:** Do not assume overlays are always
directories.  Code that reads overlays should use the `list_overlays`
and `find_all_quads_dirs` functions in `hord/quad.py`, which abstract
over the storage mechanism.


## 9. Design Principles

1. **Overlays are non-overlapping by default.**  Predicate routing
   ensures that each quad lands in exactly one overlay.  This
   eliminates merge conflicts between overlay types.

2. **Views are ephemeral.**  A composed view (reading from multiple
   overlays) is never stored.  It is computed on demand and discarded
   after use.  This means overlays can be updated independently
   without invalidating cached views.

3. **The territory is not an overlay.**  Content files (org, markdown)
   are the territory.  Overlays are maps.  A bad overlay cannot
   corrupt content.  Deleting all overlays and re-running `hord
   compile` regenerates them from the territory.

4. **Extensibility through convention.**  New overlay types are added
   by creating a directory and routing predicates to it.  No schema
   changes, no migration scripts, no version bumps.  The system is
   designed for overlay types that don't exist yet.
