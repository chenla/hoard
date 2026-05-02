# Why UUIDs, Not Filenames

**Decision:** Every entity in a hord is identified by a UUID. All relationships point at UUIDs, never at filenames, titles, or any other mutable string.

## Context

Every knowledge tool needs an identity mechanism — a way to say "this thing" unambiguously. The choice of identity mechanism determines the system's resilience to change.

## Options Considered

1. **Filenames** (Obsidian, most wikis) — the file `Kanban.md` is the identity. Simple. Breaks on rename.

2. **Titles** (wiki pages) — the page titled "Kanban" is the identity. Breaks on retitle. Breaks on duplicate titles.

3. **Paths** (folder-based systems) — `/concepts/manufacturing/Kanban.md` is the identity. Breaks on reorganization. Encodes hierarchy into identity.

4. **Content hashes** (git blob SHA, IPFS CID) — the identity is derived from the content. Changes when content changes. Useful for provenance, not for identity.

5. **UUIDs** (Hoard, org-roam, some databases) — a random 128-bit identifier assigned at creation. Never changes. Independent of name, title, path, or content.

## Why This One

UUIDs are the only option where identity survives every operation a user performs on their knowledge base:

| Operation | Filename | Title | Path | Content Hash | UUID |
|---|---|---|---|---|---|
| Rename file | Breaks | OK | Breaks | OK | OK |
| Edit title | OK | Breaks | OK | Breaks | OK |
| Move to new folder | OK | OK | Breaks | OK | OK |
| Edit content | OK | OK | OK | Breaks | OK |
| Translate to Japanese | Breaks | Breaks | Breaks | Breaks | OK |
| Fork to another hord | Breaks | Breaks | Breaks | Breaks | OK |

The cost is readability — `d4e5f6a7-1001-4000-8000-000000000011` is not human-friendly. Hoard mitigates this by using human-readable filenames and titles for display, while UUIDs work silently underneath. You never type a UUID; you type a title and the system resolves it.

## The Library Science Parallel

This is the same problem libraries solved with authority control numbers. The Library of Congress assigns control numbers (LCCN) to every author and subject. The LCCN for Mark Twain is `n 79021164`. It doesn't matter that his real name was Samuel Clemens, or that he also published as "S.L. Clemens" — the LCCN is the stable peg. Names are labels that hang from it.

In Hoard, UUIDs play the role of LCCN, and UF (Used For) relations play the role of cross-references. The concept "Kanban" is `d4e5f6a7-1001-4000-8000-000000000011`. It's also 看板, also "signboard system," also "pull scheduling." All UF entries pointing at the same UUID.

## Tradeoffs Accepted

- **Opacity.** UUIDs carry no information about what they identify. You can't look at a UUID and know it's a concept about manufacturing. This is intentional — embedding meaning in identifiers is a form of coupling that breaks when the meaning changes.

- **No natural ordering.** UUIDs don't sort chronologically or alphabetically. The index (`index.tsv`) provides path-to-UUID mapping for tools that need ordered listings.

- **Bootstrapping.** The first time you reference an entity, you need to look up its UUID. In Emacs, `hord-find` provides completing-read by title. In the CLI, `hord query` accepts titles and filenames, not just UUIDs.

## Provenance

RFC 4122 (2005) defines UUID v4 (random generation). The principle of stable identifiers independent of mutable attributes is foundational to both database design (surrogate keys, Codd 1970) and library science (authority control, Cutter 1876). The specific application to personal knowledge management — every note gets a UUID at creation — was pioneered by org-roam (Jethro Kuan, 2020) and adopted by Hoard with the additional guarantee that all relationships resolve to UUIDs, not just org-mode `id:` links.
