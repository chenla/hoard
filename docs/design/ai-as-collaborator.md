# AI as Essential Collaborator

**Decision:** Hoard is designed for AI/agent use first, human use second. The structured metadata format exists primarily because it makes AI agents effective; human convenience is a welcome side effect.

## Context

Most knowledge tools are designed for human users and treat AI integration as an afterthought — a chatbot bolted onto a search API. Hoard inverts this: the data structures are chosen to be maximally useful to AI agents, and the human interface is built on top of the same plumbing.

## The Problem AI Solves

Library science proved that controlled vocabularies, authority records, and thesaurus relations work at scale. These systems organize the Library of Congress, PubMed, and the Art & Architecture Thesaurus — millions of records, navigable and maintainable.

But these systems require relentless human maintenance. Cataloging a single book properly — assigning subject headings, establishing authority records, creating cross-references — takes a trained librarian minutes per item. At personal scale, nobody has that discipline. Every Zettelkasten eventually becomes a graveyard of unlinked notes.

AI changes the equation. The tedious, systematic, high-volume work of maintaining structured metadata is exactly what AI handles well:

- **Classification:** "This card is about a person, not a concept. Change its type."
- **Linking:** "These three cards share two tags and similar titles. They should be RT-linked."
- **Deduplication:** "These two cards describe the same concept with different names. Merge and add UF."
- **Enrichment:** "This work card has a citekey but no original publication date. WorldCat says 1859."
- **Staleness detection:** "You edited this card but didn't recompile. The metadata is stale."

The human provides judgment. The AI provides labor. Neither can maintain the system alone.

## What "AI-First" Means in Practice

### Structured over natural language

A quad like `d4e5f6a7 v:bt c348132e a1b2c3d4` is trivial for an agent to parse, validate, and extend. A sentence like "Kanban is a component of the Toyota Production System" requires natural language understanding to extract the same information — and the extraction is lossy and unreliable.

By storing relationships as typed quads, Hoard gives AI agents a representation they can work with directly, without the uncertainty of NLP extraction.

### MCP as the primary interface

The MCP server exposes the same functions as the CLI. An agent can query, create, compile, search, and modify a hord without any special knowledge beyond the tool descriptions. The structured output means the agent can process results programmatically, not by parsing human-readable text.

### The migration walkthrough

The migration guide (MIGRATION.md) is written as a human-AI collaboration script. The human provides the raw material (a directory of notes). The AI does the structural work (classify, deduplicate, link, enrich). The human reviews and corrects. This is the intended workflow — not a human doing everything alone, and not an AI doing everything unsupervised.

### Glossary cards as self-documentation

When an AI agent encounters an unfamiliar term in a hord, it can query the glossary card for that term. The card provides definition, examples, provenance, and relationships — everything the agent needs to use the term correctly. The hord documents itself in a form that AI can read.

## Tradeoffs Accepted

- **Not a human-first UX.** The CLI is powerful but not pretty. The card format has property drawers and relation lines that most people would not write by hand. The assumption is that you'll use Emacs (hord.el), the web interface, or AI to interact with cards — not edit raw org-mode.

- **Maintenance is a feature, not a bug.** Hoard requires compilation, triage, and periodic cleanup. These are designed as AI-assisted activities, not manual chores. If you don't have access to AI assistance, the overhead is higher than a flat wiki.

- **Trust boundary.** An AI agent that can create and modify cards can also introduce errors. The safety nets are: git (revert bad changes), territory/map separation (bad metadata can't corrupt content), and the compile model (derived data is always re-derivable).

## Provenance

The design assumption that AI is an essential collaborator, not a nice-to-have, emerged from the observation that library-grade metadata systems consistently fail when deployed for personal use — not because the structures are wrong, but because the maintenance burden exceeds what a single human can sustain. Karpathy's LLM Wiki insight ("the AI does the grunt work") applies with even more force to structured metadata than to prose: the structures are more valuable *and* more labor-intensive, making AI assistance not optional but necessary.

This is a bet on a specific future: that AI assistance for knowledge work will be as common as spell-checking is today. Hoard is designed for that future. If it arrives (and it is arriving), the structured metadata will compound in value. If it doesn't, the metadata is still useful — just harder to maintain.
