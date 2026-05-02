# Metadata Is Data

**Decision:** In Hoard, metadata and data are described using the same structures. There is no privileged layer. Quads describe cards. Cards describe quads. The vocabulary is itself a set of cards. The system is homoiconic.

## Context

Most systems draw a hard line between "content" and "metadata about content." A database has tables and it has a schema; the schema is not a table. A wiki has pages and it has categories; the categories are not pages (or if they are, they're second-class pages in a special namespace). An org-roam database has notes and it has a SQLite cache; the cache is not a note.

This distinction feels natural but it creates a structural asymmetry: tools that work on content don't work on metadata, and vice versa. You can search your notes but not your schema. You can version your files but not your index. You can share your content but not your vocabulary.

## The Homoiconic Principle

Hoard collapses this distinction. Everything is described the same way:

- **Cards are works.** A card has an author, a creation date, versions in git, rendered forms in HTML. WEMI applies to cards themselves, not just to what cards describe. A fork is an Expression. A rendered page is a Manifestation.

- **Quads are files.** The compiled metadata in `.hord/quads/` is plain TSV files in a git repo. They have blob hashes. They show up in diffs. They can be described by other quads.

- **The vocabulary is cards.** `terms.tsv` defines predicates, but a glossary card like "Controlled Vocabulary" *uses* those predicates (BT, NT, RT, UF) to describe itself. The card about thesaurus relations is structured using thesaurus relations.

- **Overlays describe overlays.** The overlay spec is a document. It could be a card. That card would live in an overlay. The system that organizes knowledge can organize knowledge about itself.

This is homoiconicity: the representation of the system is expressed in the system's own structures. In Lisp, code is data and data is code. In Hoard, metadata is data and data is metadata.

## Why This Matters

**Tooling works everywhere.** `hord query` works on a concept card, a person card, a tag card, and a vocabulary term. `hord link` can relate any entity to any other entity. There's no special-case handling for "meta" entities. The glossary is just cards. The vocabulary is just a TSV file. The index is just another derived artifact.

**The system can describe itself.** When an AI agent reads a hord, it can understand the vocabulary by querying vocabulary cards. It can understand the overlay structure by reading the overlay spec card. It doesn't need a separate "meta-API" or documentation format — the hord *is* its own documentation, expressed in its own structures.

**Progressive formalization.** A thought starts as a scratch pad entry (unstructured text). It becomes a capture card (has a UUID, maybe tags). It becomes a concept card (typed, with thesaurus relations). It becomes a glossary entry (with definition, examples, provenance). At every stage, it's the same kind of thing — a card described by quads. The formalization is in the richness of the metadata, not in a change of representation.

## Tradeoffs Accepted

- **Circularity.** A system that describes itself can feel circular. The Controlled Vocabulary card uses controlled vocabulary terms to describe controlled vocabularies. This is a feature (self-consistency) but it means the system requires bootstrapping — you need some terms before you can define terms.

- **No privileged ground.** There's no "meta-level" you can trust unconditionally. If a vocabulary term is mislabeled, the system will propagate the mislabel through every display that uses it. The safety net is git (revert to a known-good state) and the territory/map principle (the compiled metadata is always re-derivable).

## Provenance

The phrase "metadata is functionally equivalent to data" appeared in early W3C discussions during the development of RDF, when the Resource Description Framework was still being sketched out. Tim Berners-Lee's original Semantic Web vision made this explicit: a web page and a statement about a web page are both resources, both addressable, both describable.

The concept of homoiconicity comes from programming language theory — Lisp (McCarthy, 1960) is the canonical example, where programs and data share the same list structure. In Hoard, the parallel is that knowledge and knowledge-about-knowledge share the same quad structure.

The connection between these traditions — library science's metadata, the Semantic Web's resource descriptions, and programming's homoiconicity — is one of Hoard's foundational insights. They are all instances of the same principle: self-describing structures enable tools that work at every level of abstraction without special cases.
