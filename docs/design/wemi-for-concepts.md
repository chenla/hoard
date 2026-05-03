# WEMI Applied to Concepts, Not Just Works

**Decision:** Every entity in a hord — not just bibliographic works — has WEMI structure. The canonical definition is one Expression. Project-specific usage is another. Persona annotations are Expression-level metadata. The Whole card stays clean; Expressions live in overlays.

## The Insight

WEMI was designed for bibliographic works. *Hamlet* the abstract work is a Whole; the First Folio is an Expression; the Penguin paperback is a Manifestation. This is well understood.

What we hadn't seen until now: **concepts are works too.** The concept "Kanban" is a Whole — the abstract idea, independent of any particular usage. But Kanban means something specific in the Toyota Production System. It means something slightly different in software development. It means something different again in your hord's structural design. And it means something in Japanese (看板) that carries connotations the English word doesn't.

Each of these is an Expression of the same Whole. They share an identity (the UUID) but they carry different contextual meaning, different relationships, different relevance. And they should never be confused with each other.

## The Architecture

### Before this insight

```
Kanban card (Whole)
  :ID:        d4e5f6a7...
  :TYPE:      wh:con
  ** Relations
     - BT :: Toyota Production System
     - UF :: 看板
  ** Notes
     (canonical definition + project-specific notes
      + persona annotations, all mixed together)
```

Everything lives in one card, one pile. The controlled vocabulary definition, your project-specific usage, your persona's relevance marks — all in the same Notes section, distinguished only by human judgment about what belongs where.

### After this insight

```
Kanban card (Whole) — content/Kanban--4.org
  :ID:        d4e5f6a7...
  :TYPE:      wh:con
  ** Relations
     - BT :: Toyota Production System
     - UF :: 看板
     - PT :: Kanban
  ** Notes
     (canonical definition only — what is Kanban,
      independent of any specific context)

Strata overlay — identity metadata
  d4e5f6a7  v:type      wh:con
  d4e5f6a7  v:title     Kanban—4
  d4e5f6a7  v:s-wo      "scheduling system..."

Structural overlay — vocabulary relationships
  d4e5f6a7  v:bt        (TPS uuid)
  d4e5f6a7  v:uf        看板
  d4e5f6a7  v:rt        (JIT uuid)

Persona overlay (researcher) — your Expression
  d4e5f6a7  v:p-relevant  true
  d4e5f6a7  v:p-priority  high
  d4e5f6a7  v:p-note      "core to Hoard's structural model"

Persona overlay (teacher) — another Expression
  d4e5f6a7  v:p-relevant  true
  d4e5f6a7  v:p-note      "good introductory example for overlay concepts"
```

The Whole card carries the canonical definition. Each overlay carries an Expression — a context-specific rendering of the same concept. The persona overlays are literally different people's (or different roles') Expressions of the same Whole.

## Why This Matters

### The controlled vocabulary stays clean

The Z39.19 definition of "Broader Term" is one Expression. Your usage of BT in Hoard's structural overlay is another Expression. A Japanese library's usage of BT (上位語) is a third. All Expressions of the same Whole, all cleanly separated. No confusion between the canonical meaning and any local variation.

### Project-specific usage doesn't pollute

When you're working on the Cambodia agriculture project and "Kanban" takes on a specific meaning in that context — virtual aggregation of smallholder farm outputs — that's a project Expression. It lives in a project-specific overlay, not in the Kanban card's Notes section. The canonical definition is untouched. When you move to a different project, you see a different Expression through a different overlay.

### Persona annotations have a home

This resolves Case 1 from the cards-as-source-code discussion. A persona annotation is not metadata about the concept — it's metadata about *your relationship to the concept in a specific role*. That's an Expression. It belongs in the persona overlay, which is exactly where it already goes. The architecture was correct; we just hadn't articulated why.

### The overhead objection dissolves

The old WEMI model for concepts would have required separate cards for each Expression — one card for "Kanban (canonical)," another for "Kanban (my research context)," another for "Kanban (Cambodia project)." That's the container model that was rejected for works, and it's equally impractical for concepts.

With Expressions as overlay metadata, there are zero extra files. The Whole card exists once. Each overlay carries its Expression of that Whole as quads. The compile step derives the quads from the card (for structural and strata) and from persona annotations (for persona overlays). Same card, multiple Expressions, no card explosion.

### AI collaboration becomes clearer

When an AI agent reads a concept card, it reads the Whole — the canonical definition. When it reads the persona overlay, it reads *your* Expression — what this concept means to you in this role. The agent can distinguish between "what Kanban is" and "why Kanban matters to Brad's research." These are different questions answered by different WEMI levels, accessed through different overlays.

## The Source Code Analogy Extended

If a card is source code, then:

- The **Whole card** is the source file — the authoritative definition.
- The **strata overlay** is the compiled type information — identity, classification.
- The **structural overlay** is the compiled dependency graph — relationships, hierarchy.
- **Persona overlays** are build configurations — different compilation targets for different contexts, all from the same source.

You don't create a separate source file for each build target. You have one source and multiple build configurations. That's what overlays are.

## Implications for Implementation

1. **Persona annotations stay in overlays, not in cards.** This is already the implementation. The design rationale is now clear: annotations are Expressions, not Whole-level properties.

2. **The card's Notes section should carry only the canonical definition.** Project-specific usage, role-specific relevance, and contextual notes belong in overlays.

3. **`hord compile` extracts the Whole.** Relations, type, title — these are Whole-level properties compiled from the source file. Persona annotations are Expression-level properties that live only in overlays and are not compiled from the card.

4. **Cross-hord identity claims (v:same-as) have a home.** They're not Whole-level properties of the card — they're assertions about the relationship between two Wholes in different hords. They belong in an overlay (federation overlay? identity overlay?), not in the card.

5. **AI suggestions that haven't been reviewed could live in a staging overlay.** A "proposed" overlay that carries suggested relations at Expression level — hypotheses about the Whole that haven't been promoted to Whole-level source code yet. Review promotes them from the staging overlay into the card (source code).

## Provenance

FRBR (IFLA, 1998) applied WEMI to bibliographic works. The Strata specification (2026) generalized it to any entity. This design note extends it one step further: WEMI applies not just to the entities described by cards, but to the cards' *meanings* across contexts. The insight connects to:

- Wittgenstein's language games (meaning is use in context)
- The Semantic Web's named graphs (the same triple means different things in different graphs)
- Database views (the same table, different projections for different consumers)
- The homoiconicity principle (if metadata is data, then Expressions of concepts are the same kind of thing as Expressions of works)

The immediate trigger was the cards-as-source-code discussion (2026-05-02), where the question "can metadata exist only in an overlay?" led to the recognition that persona annotations are Expressions, not properties — and from there to the generalization that all concepts have WEMI structure.
