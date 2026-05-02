# Overlays as Directories, Not Git Branches

**Decision:** Metadata overlays are subdirectories of `.hord/overlays/`, not separate git branches.

## Context

Hoard's overlay model separates different kinds of metadata: strata (identity), structural (organization), persona (role-specific annotations). The original design envisioned each overlay as a separate git branch — never merged, composed at read time. The implementation uses directories instead.

## Options Considered

1. **Git branches** — each overlay on its own branch. True isolation. Independent version histories. Composition via multi-branch reads.

2. **Directories** — each overlay as a subdirectory of `.hord/overlays/`. Single branch. Composition by reading from multiple directories.

## Why This One

Directories are simpler to work with in every dimension:

**No branch management.** Users don't need to understand git branches to use overlays. There's no switching, no checkout, no "which branch am I on?" confusion. The entire hord state is visible at all times.

**Atomic compilation.** `hord compile` writes to multiple overlay directories in a single run. With branches, it would need to checkout each branch, write quads, commit, switch back — a fragile, slow operation that's hostile to interruption.

**Standard git workflows.** Push, pull, clone, diff — all work normally. A single branch with directories is what every git user expects. Multi-branch overlays would require custom tooling for every git operation.

**Predicate routing guarantees non-overlap.** The key insight that made directories viable: each quad lands in exactly one overlay, determined by its predicate. Strata predicates go to `strata/`, structural predicates go to `structural/`. There are no merge conflicts because the overlays don't share predicates. Branches would solve a problem (concurrent edits to the same file) that predicate routing eliminates.

## Tradeoffs Accepted

- **Shared version history.** All overlays share one git history. A commit that recompiles quads touches both strata and structural overlay directories. With branches, you could see "only structural changes since Tuesday." With directories, you'd need to filter the diff.

- **No independent access control.** On a single branch, anyone with write access can modify any overlay. Branches could have per-branch permissions (GitHub branch protection, for example). The directory approach relies on convention and review, not enforcement.

- **Migration path.** If the branch model is ever needed (institutional hords with independent overlay maintainers), migrating from directories to branches requires moving files and rewriting history. Not impossible, but not free.

## When Branches Might Return

The branch model becomes compelling when:

- Different people or teams maintain different overlays
- Overlays need independent approval workflows (PR per overlay)
- Version history needs to be auditable per overlay (compliance)

These are institutional requirements, not personal ones. The directory model serves personal and small-team use well. The code already abstracts over the storage mechanism (`list_overlays`, `find_all_quads_dirs`), so the migration path exists.

## Provenance

The original multi-branch design came from thinking about Hoard as a library system where a cataloger maintains the strata overlay and subject specialists maintain structural overlays — a division of labor common in large libraries. The pivot to directories came from the practical reality that personal knowledge management doesn't have that division of labor, and the predicate routing mechanism eliminates the main advantage of branch isolation (non-overlapping writes).
