# Context Cloud Specification

Status: Working Draft — 2026-05-26

## Overview

A **context cloud** is a rendering of a holon as a standalone article
surrounded by anchored reference cards. The article body is the primary
content; reference cards appear in the margin at the point where the
text references them.

This is the publication format for the Holon layer of the publishing
stack (YouTube → Substack → **Holon** → B>I Net → ICAS).

## Design Principles

1. **The writing is the curation.** Cards appear because the text
   references them. There is no separate curation step.

2. **Anchored, not listed.** Each reference card is connected to a
   specific passage in the text, not floating alongside it.

3. **Self-contained.** A context cloud renders as a single deployable
   directory (`index.html` + assets) that works offline, can be
   cloned, and requires no server.

4. **Graceful degradation.** On wide screens, cards appear in the
   margin. On narrow screens, they collapse to expandable footnotes.
   In plain text or LaTeX export, markers are ignored or rendered as
   endnotes.

## Holon Structure for Context Cloud

A context cloud holon has one **primary card** (the article body) and
zero or more **reference cards** (the context cloud). The primary card
is designated in the holon definition:

```org
:PROPERTIES:
:ID:       <holon-uuid>
:TYPE:     wh:holon
:END:
#+TITLE: The Solvay Photo

** Description

Post 1 of Screed — the 1927 photograph as origin point.

** Membership

Cards tagged ~screed-t1, plus:
- 01-the-solvay-photo--article

** Primary

01-the-solvay-photo--article

** Expression

Prefer: screed-t1
Fallback: whole

** Order

1. wh:per (alphabetical)
2. wh:evt
3. wh:con
4. wh:wrk
```

### Primary Section

The `** Primary` section names the card (by slug) that contains the
article body. This card is rendered as the main content. All other
member cards are available as margin references.

Compiles to: `v:h-primary <holon-uuid> <primary-card-uuid>`

## Inline Reference Markers

Reference cards are anchored to the article text using org-mode's
inline export snippet syntax:

```
@@margin:Card_Slug--N@@
```

### Syntax

```
@@margin:SLUG@@           — standard margin reference
@@margin:SLUG:LABEL@@     — with custom label (overrides card title)
@@margin:SLUG:LABEL:NOTE@@  — with inline note appended to card
```

Where:
- `SLUG` is the card's filename stem (e.g., `Albert_Einstein--7`)
- `LABEL` (optional) overrides the card title in the margin
- `NOTE` (optional) adds a brief contextual note specific to this
  reference (rendered below the card content in the margin)

### Examples

```org
Von Neumann arrived at Solvay already skeptical of
determinism. @@margin:John_von_Neumann--solvay-1927@@

The Prussian education system @@margin:Prussian_Education--4:The
model that shaped American schools@@ was imported specifically
because it produced compliant workers.

Thompson's "wave speech" @@margin:Thompson_Wave_Speech--14::The
high-water mark passage connects directly to Screed's arc of
lost momentum@@ remains the definitive elegy for the
counterculture.
```

### Why `@@margin:...@@`?

Org-mode's `@@backend:value@@` syntax is designed for format-specific
inline content. It is:
- Ignored by non-matching export backends (LaTeX, ASCII, etc.)
- Already parsed by org's export engine
- Familiar to org-mode users
- Does not conflict with links, emphasis, or other markup

The `margin` backend is recognized only by the Hoard HTML renderer.

## Vocabulary

New terms added to `vocab/terms.tsv`:

| Term | Label | Scope Note |
|------|-------|------------|
| `v:h-primary` | PRIMARY | Designates the primary content card within a holon |
| `v:h-anchor` | ANCHOR | Links a reference card to a position in the primary text |

Note: `v:h-zone` and `v:h-pos` are NOT needed. Zone is always
"margin" (the only layout position). Position is determined by the
order of `@@margin:...@@` markers in the source text. The text is the
authority, not metadata.

## Compilation

When a holon with a `** Primary` section is compiled:

1. Generate `v:h-primary` quad in structural overlay
2. Parse the primary card's source for `@@margin:SLUG@@` markers
3. For each marker, verify the slug matches a holon member
4. Generate `v:h-anchor` quads: `<primary-uuid> v:h-anchor <ref-uuid>`
5. Warn if a marker references a card not in the holon membership
6. Warn if a member card is never referenced (orphan in context cloud)

## HTML Rendering

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  TITLE                                                       │
├────────────────────────────────────┬─────────────────────────┤
│                                    │                         │
│  Article body text flows here      │  ┌───────────────────┐  │
│  in a readable measure (~60ch).    │  │ Card: Von Neumann │  │
│  When a @@margin:...@@ marker      │  │ Expression text   │  │
│  appears, the referenced card      │  │ from the solvay   │  │
│  is placed in the right margin     │  │ expression card.  │  │
│  at that vertical position.        │  └───────────────────┘  │
│                                    │                         │
│  The text continues below and      │                         │
│  the next marker places the next   │  ┌───────────────────┐  │
│  card further down the margin.     │  │ Card: Operator    │  │
│                                    │  │ Algebra           │  │
│                                    │  │ Definition and    │  │
│                                    │  │ context...        │  │
│                                    │  └───────────────────┘  │
│                                    │                         │
├────────────────────────────────────┴─────────────────────────┤
│  Footer: metadata, provenance, clone instructions            │
└──────────────────────────────────────────────────────────────┘
```

### Wide screen (>960px)

- Article body: left column, ~60ch measure
- Margin cards: right column, ~30ch, positioned at the vertical
  offset of their `@@margin:...@@` marker
- Cards styled as compact reference panels (title, type badge,
  scope note or first paragraph, link to full card)

### Narrow screen (<960px)

- Article body: full width
- Margin markers become numbered superscripts (like footnotes)
- Tapping/clicking a superscript expands the card inline or
  scrolls to a footnote section at the bottom

### Card rendering in margin

Each margin card displays:

1. **Title** — card title, or custom label if provided in the marker.
   Linked to the full card page (if deployed within a hord site)
   or to the source (if standalone).

2. **Type badge** — small, colored indicator (Concept, Person, Work,
   Event, etc.)

3. **Body text** — resolved by cascade (first non-empty wins):

   | Priority | Source | When to use |
   |----------|--------|-------------|
   | 1 | **Inline note** | Author wrote `@@margin:SLUG::note text@@`. Context-specific; composed at the point of reference. |
   | 2 | **Expression card** | Holon has an expression preference and a matching expression card exists for this slug. Purpose-written for this context. |
   | 3 | **Scope note** | The card's scope note property (entity docstring). Usually 1-2 sentences. The default for most cards. |
   | 4 | **First paragraph of Notes** | Fallback if no scope note exists. Extracted from the card body. |

   The cascade means most cards "just work" with their scope note.
   When you need context-specific framing, add an inline note at the
   marker. When you've already invested in expression cards for the
   holon, those are picked up automatically.

4. **Truncation** — margin cards are truncated at ~150 words with a
   "read more →" expansion. Scope notes are brief by convention
   (they are docstrings). Inline notes should be 1-2 sentences.
   Expression cards may be longer since they are purpose-written,
   but the truncation still applies in the margin; expansion reveals
   the full text.

   These thresholds are provisional. Adjust based on experience
   with real content.

### Standalone deployment

The renderer produces a directory:

```
article-slug/
├── index.html          # self-contained article + context cloud
├── cards/              # individual card pages (optional)
│   ├── card-slug-1.html
│   └── card-slug-2.html
└── assets/
    └── style.css       # Tufte-inspired stylesheet
```

If `--standalone` flag is used, all CSS is inlined and the directory
contains only `index.html` (single file, zero dependencies).

## Integration with Publishing Stack

| Layer | What it gets |
|-------|-------------|
| YouTube | Script derived from article body |
| Substack | Article body exported as HTML (markers stripped) |
| Holon | Full context cloud as standalone site |
| B>I Net | Same holon, cloneable into member's hord, editable |

The same source file serves all layers. The `@@margin:...@@` markers
are simply ignored by non-Hoard exporters.

## Future Extensions

- **`@@sidebar:SLUG@@`** — left-column cards for extended digressions
- **`@@figure:SLUG@@`** — inline figures from blob attachments
- **`@@exec:SLUG@@`** — executable/interactive blocks (Jupyter vision)
- **Card-to-card anchoring** — references between margin cards
- **Bidirectional anchoring** — card knows which articles reference it
