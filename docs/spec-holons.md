# Hoard Holon Specification

**Status:** Working Draft, 2026-05-08
**Audience:** Implementors building tools that read or write hord holons
**Prerequisite:** Overlay Specification, Vocabulary Specification, WEMI design note

---

## 1. Overview

A hord is a territory.  Most hords contain a single collection of
cards, and most users will work with that collection as a whole.  But
some territories contain multitudes — the same cards need to appear
in different contexts, sometimes with genuinely different content.

A **holon** is a named subset of a hord's cards, assembled for a
specific purpose.  The word comes from Arthur Koestler's *The Ghost in
the Machine* (1967): a holon is something that is simultaneously a
whole in its own right and a part of a larger whole.  A card in a
holon is both a standalone entity and a component of the holon's
particular view of the territory.

Holons solve a class of problems that filters and queries cannot:

- **Temporal context.** "Show me these 29 physicists as they were in
  October 1927" — not filtered biographies, but genuinely different
  cards written for that moment.

- **Multi-audience presentation.** The same hord serves a Screed
  introductory post (20 cards, accessible framing), a deep technical
  dive (200 cards, full detail), and a presentation (40 cards,
  strategic framing).

- **Contradictory views.** A historian's reading and a physicist's
  reading of the same conference produce different — sometimes
  incompatible — interpretations.  Both are valid.  A territory
  can hold both without one overwriting the other.

For simple hords, there is no functional difference between the
territory and its default holon.  The mechanism adds nothing until
you need it.


## 2. Conformance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document
are to be interpreted as described in RFC 2119.

A **holon** is a card of type `wh:holon` whose body defines a named
subset of the hord.  An **expression card** is a card linked to a
Whole card via the `v:s-eo` predicate, providing alternative content
for that Whole in a specific context.


## 3. Relationship to Existing Architecture

Holons do not introduce a new overlay type.  They compose from
existing mechanisms:

| Mechanism         | Where it lives      | Role in holons                    |
|------------------|--------------------|------------------------------------|
| `wh:holon` card  | `content/`          | Defines the holon (membership, expression preference, ordering) |
| Expression cards  | `content/`          | Alternative content for a Whole in a specific context |
| `v:s-eo` quad     | `strata` overlay    | Links an expression card to its Whole |
| `v:h-member` quad | `structural` overlay| Links a holon to its member cards  |
| `v:tag` quad       | `structural` overlay| Tags cards for filter-based membership |

**Design rationale:** Holons are an application of WEMI to cards
themselves.  The "WEMI Applied to Concepts" design note established
that every entity has WEMI structure; the "E&M as Metadata" design
note established that Expressions are metadata properties, not
containers.  Holons extend this: an expression card is a new card
file that carries alternative content, linked to its Whole through
the strata overlay.  The holon definition card lives in the structural
overlay because membership is an organizational concern — it answers
"how are these cards grouped?" not "what are they?"


## 4. Vocabulary Additions

### 4.1. Card Type

| Term       | Label  | Scope note                                       |
|-----------|--------|--------------------------------------------------|
| `wh:holon` | Holon  | A named subset of hord cards assembled for a specific context or purpose |

### 4.2. Predicates

| Term         | Label    | Scope note                                     | Overlay    |
|-------------|----------|------------------------------------------------|------------|
| `v:h-member` | MEMBER   | Card is a member of this holon (subject=holon, object=card UUID) | structural |
| `v:h-expr`   | EXPR-PREF| Expression preference tag for this holon (subject=holon, object=tag label) | structural |
| `v:h-order`  | ORDER    | Ordering position within the holon (subject=card UUID, object=integer, context=holon UUID) | structural |
| `v:h-cascade`| CASCADE  | This holon inherits from another (subject=holon, object=parent holon UUID) | structural |

All holon predicates use the `v:h-` namespace prefix.  They route to
the structural overlay because they describe organization, not
identity.

The `v:h-cascade` predicate is reserved for future use.  It MUST NOT
be implemented until the cascade composition rules are specified.


## 5. Expression Cards

An expression card provides alternative content for a Whole card
within a specific context.  It is a regular card file — org-mode or
Markdown — with its own UUID, linked to its Whole via the existing
`v:s-eo` predicate.

### 5.1. Creating an Expression Card

An expression card MUST have:

1. **Its own UUID.** An expression is a distinct entity, not a copy.
2. **A `v:s-eo` quad** linking it to the Whole card's UUID.
3. **A `v:type` quad** with the same type as the Whole card (a person
   expression is still `wh:per`).
4. **A `v:tag` quad** with the expression tag (e.g., `solvay-1927`),
   matching the holon's expression preference.

An expression card SHOULD follow the naming convention:

```
<whole-slug>--<expression-tag>.<ext>
```

For example:

```
content/einstein-albert.org             ← Whole card
content/einstein-albert--solvay-1927.org ← Expression card
```

The `--` delimiter makes the relationship visible in the filesystem
without requiring tools to read quads.  This is a convention, not a
requirement — tools MUST use the `v:s-eo` quad to resolve
expression relationships, not filename parsing.

### 5.2. Expression Card Content

An expression card is **standalone**.  It contains all the content
needed for its context.  It is not a diff or delta against the
Whole card.

**Design rationale:** The standalone approach accepts content
duplication in exchange for simplicity.  Each expression card is
readable on its own, editable without reference to the Whole, and
compilable without a merge step.

This is a deliberate tradeoff.  A delta mechanism (where the
expression carries only what differs from the Whole) would eliminate
duplication but require a merge engine at read time and a conflict
resolution model.  The delta approach is not precluded by this spec
and MAY be added in a future version, but implementations MUST NOT
require it.

### 5.3. When to Create Expression Cards

Expression cards are appropriate when the context demands
**genuinely different content**, not just a different selection of
existing content.

| Situation                                         | Use expression card? |
|--------------------------------------------------|---------------------|
| Einstein's full biography                         | No — this is the Whole |
| Einstein as he was in October 1927                | Yes — different content, scoped to that moment |
| Einstein for a children's encyclopedia            | Yes — different framing, different detail level |
| Einstein omitted from a quantum-only card set     | No — this is membership (the holon decides) |
| Einstein with a relevance note for a presentation | No — this is a persona annotation |

The test: **if the text of the card would be different, it's an
expression.  If only the selection or annotation changes, it's
membership or a persona overlay.**


## 6. Holon Definition Cards

A holon definition is a card of type `wh:holon` that specifies which
cards belong to the holon, which expression to prefer, and in what
order to present them.

### 6.1. Card Structure

```org
:PROPERTIES:
:ID:       <holon-uuid>
:TYPE:     wh:holon
:END:
#+TITLE: Solvay 1927

29 physicists as they were in October 1927 — the fifth Solvay
Conference on Electrons and Photons.

* Membership

Cards tagged ~solvay-1927, plus:
- solvay-conference-1927 (wh:evt)
- solvay-institutes (wh:org)
- solvay-1927-photo (wh:media)

* Expression

Prefer: solvay-1927
Fallback: whole

* Order

1. wh:evt (the conference itself)
2. wh:per (alphabetical by title)
3. wh:org
4. wh:media
```

The Markdown equivalent uses the same heading structure with `##`
headings.

### 6.2. Membership

Membership is defined in the holon card body and compiled to
`v:h-member` quads.  A card can be a member of a holon in two ways:

1. **Explicit.** The holon card lists the card by slug or UUID.
2. **Tag-based.** The holon card specifies a tag; any card with a
   matching `v:tag` quad is a member.

When both explicit and tag-based membership are present, the result
is the union.

**Membership lives in the holon, not in the cards.**  A card does not
know which holons include it.  This is the key design constraint that
avoids the attribute trap — cards do not accumulate holon membership
tags.  Tags like `solvay-1927` are ordinary `v:tag` quads that exist
for their own descriptive purpose; the holon *reads* those tags to
compute membership, but doesn't require cards to carry them.

### 6.3. Expression Preference

The `Expression` section specifies which expression tag to prefer
when a member card has multiple expressions:

- **Prefer:** The expression tag to use.  When a member card has an
  expression card tagged with this value (via `v:tag`), the holon
  presents the expression card instead of the Whole.
- **Fallback:** What to show when no matching expression exists.
  `whole` means show the Whole card.  `omit` means exclude the card
  from the holon if it lacks the preferred expression.

### 6.4. Ordering

The `Order` section defines presentation sequence.  Cards are ordered
first by the type sequence listed, then by the sort criterion within
each type (default: alphabetical by `v:title`).

Ordering is compiled to `v:h-order` quads — integer positions stored
in the structural overlay.

### 6.5. The Default Holon

Every hord has an implicit **default holon**: all cards, no expression
preference, alphabetical ordering.  This is not stored anywhere — it
is the result of querying the hord without a holon filter.  Simple
hords never create a `wh:holon` card and never encounter the holon
mechanism.


## 7. Compilation

When `hord compile` processes a `wh:holon` card, it:

1. Parses the Membership section to identify member cards.
2. Generates `v:h-member` quads (holon UUID → member card UUID) in
   the structural overlay.
3. Reads the Expression Preference and stores it as a `v:h-expr`
   quad on the holon card.
4. Parses the Order section and generates `v:h-order` quads for
   each member card in the structural overlay.

Expression cards are compiled like any other card.  The `v:s-eo` quad
linking them to their Whole is routed to the strata overlay by
existing predicate routing rules (the `v:s-` prefix routes to strata).


## 8. Querying a Holon

A tool that wants to present a holon's view of the hord:

1. Reads the holon card's `v:h-member` quads to get the member list.
2. For each member, checks whether an expression card exists with the
   holon's preferred expression tag (via `v:s-eo` + `v:tag` match).
3. If an expression exists, presents that card.  Otherwise, presents
   the Whole card (or omits, per the fallback rule).
4. Orders the result by `v:h-order` quads.

This is a read-time operation.  No new overlay is created.  The view
is ephemeral — consistent with the overlay spec's principle that
"views are ephemeral."


## 9. Worked Example: Solvay 1927

### Territory (the full hord)

```
content/
  einstein-albert.org                    ← Whole (wh:per)
  bohr-niels.org                         ← Whole (wh:per)
  curie-marie.org                        ← Whole (wh:per)
  heisenberg-werner.org                  ← Whole (wh:per)
  solvay-conference-1927.org             ← Whole (wh:evt)
  solvay-institutes.org                  ← Whole (wh:org)
  solvay-1927-photo.org                  ← Whole (wh:media)
  einstein-albert--solvay-1927.org       ← Expression
  bohr-niels--solvay-1927.org            ← Expression
  curie-marie--solvay-1927.org           ← Expression
  heisenberg-werner--solvay-1927.org     ← Expression
  solvay-1927.org                        ← Holon definition (wh:holon)
```

### Strata overlay (compiled)

```
<einstein-expr-uuid>  v:s-eo   <einstein-whole-uuid>
<bohr-expr-uuid>      v:s-eo   <bohr-whole-uuid>
<curie-expr-uuid>     v:s-eo   <curie-whole-uuid>
<heisenberg-expr-uuid> v:s-eo  <heisenberg-whole-uuid>
```

### Structural overlay (compiled)

```
<holon-uuid>  v:h-member  <einstein-whole-uuid>
<holon-uuid>  v:h-member  <bohr-whole-uuid>
<holon-uuid>  v:h-member  <curie-whole-uuid>
<holon-uuid>  v:h-member  <heisenberg-whole-uuid>
<holon-uuid>  v:h-member  <solvay-conference-uuid>
<holon-uuid>  v:h-member  <solvay-institutes-uuid>
<holon-uuid>  v:h-member  <solvay-photo-uuid>
<holon-uuid>  v:h-expr    solvay-1927

<einstein-whole-uuid>       v:h-order  2   <holon-uuid>
<bohr-whole-uuid>           v:h-order  3   <holon-uuid>
<curie-whole-uuid>          v:h-order  4   <holon-uuid>
<heisenberg-whole-uuid>     v:h-order  5   <holon-uuid>
<solvay-conference-uuid>    v:h-order  1   <holon-uuid>
<solvay-institutes-uuid>    v:h-order  6   <holon-uuid>
<solvay-photo-uuid>         v:h-order  7   <holon-uuid>
```

### Query result for holon "Solvay 1927"

1. Solvay Conference 1927 — Whole card (no expression needed)
2. Einstein — expression card (as he was in 1927)
3. Bohr — expression card
4. Curie — expression card
5. Heisenberg — expression card
6. Solvay Institutes — Whole card
7. Solvay 1927 photograph — Whole card


## 10. Design Principles

1. **The territory is not a holon.**  The hord's full card set is the
   territory.  A holon is a map — a deliberate selection and
   arrangement of cards for a purpose.  Like all maps, it is
   opinionated and incomplete.

2. **Membership is the holon's concern, not the card's.**  Cards do
   not carry holon membership markers.  A card is a card.  The holon
   decides what to include.

3. **Expressions are transformative, not cosmetic.**  An expression
   card exists because the context demands genuinely different
   content.  If a filter or annotation suffices, do not create an
   expression card.

4. **Simple hords pay nothing.**  A hord with no `wh:holon` cards
   behaves exactly as it does today.  The default holon is implicit.

5. **Start standalone, defer deltas.**  Expression cards are
   standalone in this version.  A delta mechanism MAY be added later
   but is not required for conformance.

6. **Defer cascading.**  Holon inheritance (`v:h-cascade`) is reserved
   for future specification.  Implementations MUST NOT act on this
   predicate until cascade composition rules are defined.


## 11. Future Directions

The following capabilities are anticipated but **not specified here**.
The current design MUST NOT preclude them:

- **Delta expressions.** An expression card that carries only the
  differences from the Whole, merged at read time.

- **Cascade composition.** A holon that inherits membership and
  ordering from a parent holon, overriding specific entries.

- **Tag scoping.** Distinguishing global hord-wide tags from
  holon-local tags, establishing an inheritance cascade.

- **Holon-aware CLI.**  Commands like `hord query --holon solvay-1927`
  or `hord list --holon solvay-1927` that present the holon's view.

- **Holon rendering.**  Exporting a holon as a standalone document
  (HTML, PDF, EPUB) — a natural fit for Screed publication.
