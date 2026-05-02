# Expression and Manifestation as Metadata, Not Containers

**Decision:** In Hoard's WEMI model, Expression and Manifestation are metadata properties on a Whole card, not separate content containers or card types.

## Context

FRBR (and Hoard's generalization, Strata) describes four levels: Whole, Expression, Manifestation, Instance. The question is whether each level gets its own card/file, or whether a single card carries metadata about all levels.

## Options Considered

1. **Separate cards per level** — a Whole card, linked to Expression cards, linked to Manifestation cards, linked to Instance cards. Full FRBR realization. Each level is a first-class entity with its own UUID.

2. **E&M as metadata on the Whole card** — one card per work. Expression and Manifestation information lives as properties (`:DATE-EXPR:`, `:DATE-WHOLE:`) and quads (`v:s-eo`, `v:s-mo`) on that card. Instances are blobs in `lib/blob/`.

## Why This One

Years of testing option 1 led to a hard-won conclusion: **separate E/M cards don't work in practice for personal knowledge management.**

The problems:

**Card explosion.** A book with one English edition and one Japanese translation generates: 1 Whole + 2 Expressions + 4 Manifestations (hardcover, paperback, EPUB, PDF per expression) + N Instances. That's 7+ cards for one book. Multiply by 4,500 works. The card count becomes unmanageable and the signal-to-noise ratio collapses.

**Navigation overhead.** To find "what do I know about Seeing Like a State?" you'd need to navigate from the Whole to its Expressions to find the one you read, then to its Manifestation to find your notes. Three hops for a basic lookup.

**Maintenance burden.** Creating an Expression card requires knowing enough about the work to distinguish expressions — which edition, which translation, which adaptation. For most works in a personal hord, you have one expression and one manifestation. The overhead of separate cards provides no value.

**The metadata approach scales.** For the common case (one work, one edition, one or two file formats), `:DATE-EXPR: 1998` and a blob in `lib/blob/` capture everything needed. For the complex case (A Christmas Carol with dozens of adaptations), you can still create separate Whole cards for each major adaptation — they're genuinely different works, not just different expressions of one work.

## Tradeoffs Accepted

- **Less rigorous than full FRBR.** A librarian would object that we're conflating levels. A work card with `:DATE-EXPR: 1998` is technically a Whole that carries Expression-level metadata. This is intentional — FRBR's rigor was designed for institutional catalogs with trained catalogers. Personal knowledge management needs a lighter touch.

- **Complex works need judgment.** When does a translation become a separate Whole vs. an Expression of the existing one? When does a revised edition cross the line? These are judgment calls that the metadata-on-Whole model defers rather than forces. The `:WEMI: W` marker says "this card has been assessed" — it doesn't say "this card's WEMI tree is complete."

- **Future enrichment path.** The Phase 2 bibliographic reconciliation skill can add Expression-level metadata progressively. A card starts as `:WEMI: W` (we know it's a Whole) and can be enriched to `WE` (we know about its Expressions) and `WEM` (we know about its Manifestations) as the skill discovers more.

## Provenance

The E&M-as-containers approach was tested extensively (several years of exploration) before this conclusion was reached. The turning point was recognizing that FRBR's four levels describe a *model* of how works relate across form, not a *file structure* for organizing content. The model is valuable; the file structure is not. Metadata carries the model without imposing the structure.

This aligns with the broader Hoard principle: the map is not the territory. E&M metadata is part of the map. Content (the actual files) is the territory. Maps describe; they don't contain.
