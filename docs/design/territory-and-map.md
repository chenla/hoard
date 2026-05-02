# Territory and Map

**Decision:** Hoard stores metadata separately from content. The `.hord/` directory is the map; your files are the territory. The map never modifies the territory.

## Context

Every knowledge tool makes an architectural choice about where metadata lives. Obsidian puts it in YAML frontmatter inside the file. Notion puts it in a cloud database. Org-roam puts it in a SQLite cache derived from the files. Each choice has consequences.

## Options Considered

1. **Inline metadata** (Obsidian model) — metadata lives inside the content file as frontmatter or properties. Simple, one file per entity, everything in one place.

2. **External database** (Notion model) — metadata in a database, content in the database too. Maximum query power. Total vendor lock-in.

3. **Derived cache** (org-roam model) — files are authoritative, database is rebuilt from them. Files are portable but the database is what makes them useful.

4. **Separate overlay** (Hoard model) — metadata in `.hord/`, content in regular files. Both in the same git repo. Both version-controlled. Neither modifies the other.

## Why This One

The separation has three properties the others lack:

**Recovery.** Delete `.hord/` entirely. Run `hord compile`. Everything regenerates. A bad map cannot corrupt your content. You can never lose your writing to a metadata bug.

**Format independence.** The same `.hord/` metadata works whether your content is org-mode, markdown, or a mix. The compile step is the bridge — it reads whatever format you use and emits quads. Adding a new format means writing a new parser, not redesigning the metadata layer.

**Non-text content.** PDFs, images, datasets, audio files all live in the territory. They can't carry inline metadata. A separate overlay means every file in the repo is a first-class citizen of the knowledge graph, whether it's a text file you wrote or a PDF you downloaded.

## Tradeoffs Accepted

- **Two places to look.** When editing a card, you see the metadata inline (org properties, markdown frontmatter) *and* the compiled version in `.hord/`. These can diverge until you recompile. `hord status` catches this, but it's a manual step.

- **Compile step required.** Unlike Obsidian where saving a file immediately updates the graph, Hoard requires `hord compile` to propagate changes to the quad store. This is intentional (derived data should be derived, not maintained in parallel) but adds a step to the workflow.

- **Duplication.** The title, type, and relations appear in both the source file and the quads. The source file is authoritative; the quads are derived. This is the same relationship as source code and compiled binaries — the duplication is the feature, not a bug.

## Provenance

The territory/map distinction comes from Alfred Korzybski's "the map is not the territory" (1931), via Gregory Bateson and the cybernetics tradition. In information science, the same principle appears as the distinction between a work and its bibliographic record. Library catalogs have always been maps of collections, not the collections themselves. Hoard applies this principle at the file system level.
