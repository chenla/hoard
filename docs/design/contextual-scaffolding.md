# Contextual Scaffolding

**Decision:** Hoard's documentation is not a traditional set of structured documents. It is a card-centric contextual scaffold where the glossary cards bear the reference weight that traditional documents carry inline.

## The Traditional Problem

Technical documentation has an impossible burden. Every document must simultaneously tell a story and define its terms. The narrative flow stops while the author explains what a "quad" is, what "BT" means, where the concept of authority control comes from, why UUIDs were chosen over filenames. The reader who already knows these things is bored. The reader who doesn't is overwhelmed. The author, trying to serve both, serves neither well.

The standard solution is a glossary at the back — an alphabetical list of definitions that nobody reads until they're confused, and then they lose their place. Or footnotes. Or inline parentheticals that fracture the prose. Every solution accepts the same premise: the document must carry its own reference burden.

Hoard rejects that premise.

## The Scaffold

In Hoard's documentation architecture, narrative documents are lighter than they would traditionally be. They tell the story, make the argument, walk through the procedure. When they encounter a concept that needs definition — "quad," "overlay," "controlled vocabulary," "WEMI" — they don't define it inline. The definition lives in a card.

The card is not a glossary entry in the traditional sense. It's a full entity in the knowledge graph: a UUID, a type, thesaurus relations (BT, NT, RT, UF), a definition, examples, provenance, references. It participates in the same structural overlay as every other card. It can be queried, linked, suggested, browsed.

This means the reference weight shifts from the documents to the cards. The cards form a scaffold — an interconnected structure that supports the narrative documents without being visible in them. You read the overlay spec and encounter "predicate routing." You don't need it explained in the spec because the Predicate Routing card exists, with its definition, its examples, its provenance, and its links to Overlay, Quad, and Controlled Vocabulary. If you need it, it's there. If you don't, the spec flows uninterrupted.

## The Taj Mahal Inversion

When the Taj Mahal was built, a massive brick scaffold rose alongside the marble dome — a structure as large as the building itself, essential during construction, demolished when the dome was complete. The scaffold bore the weight of the unfinished structure. When the structure could stand on its own, the scaffold disappeared.

A contextual scaffold inverts this. It is invisible until needed, then it appears — fully formed, cross-referenced, authoritative. It doesn't disappear because the work is never finished. A knowledge graph is always becoming. The scaffold is not temporary support for a static artifact; it is the permanent load-bearing foundation for a living system.

The scaffold bears the reference weight so the narrative documents don't have to. The narrative documents bear the argumentative weight so the scaffold doesn't have to. Each does what it's good at. Neither pretends to do both.

## Closing the Circle

This is the homoiconicity principle applied to documentation:

- **In Lisp:** code is data and data is code. Programs manipulate themselves using the same structures they're built from.

- **In the Semantic Web:** metadata is functionally equivalent to data. Everything is a resource. Everything is describable.

- **In Hoard:** the documentation scaffold is built from the same cards it documents. The Controlled Vocabulary card uses controlled vocabulary relations (BT, NT, RT, UF) to describe itself. The Thesaurus Relation card has thesaurus relations to the cards that define thesaurus relations. The Homoiconicity card demonstrates homoiconicity.

The scaffold is not a separate system that describes the primary system. It *is* the primary system, describing itself. The map and the territory converge — not because the map replaces the territory, but because the territory contains the maps it needs, expressed in its own structures.

Traditional documentation stands outside the system it describes. Hoard's documentation stands inside it. The cards are simultaneously the thing being documented and the documentation itself. This is not a metaphor. It is a structural property of the architecture.

When someone reads the Architecture Decision Record for "Why TSV, Not JSON" and wants to understand what a quad is, they query the Quad card. That card was compiled into quads. Those quads were stored as TSV. The explanation of the format is stored in the format it explains. The circle is closed.

## Practical Implications

**For authors:** Write narrative documents that tell stories and make arguments. Don't explain terms inline — link to cards. If a card doesn't exist for a concept you need, create one. The card will serve every future document that references the same concept.

**For readers:** If you know the terminology, read the narrative docs straight through. If you encounter an unfamiliar term, query the card (`hord query <term>` or click through in `hord web`). The card gives you definition, examples, and provenance. Come back to the narrative without having lost the thread.

**For AI agents:** The glossary cards are structured metadata that agents can read without parsing prose. An agent working with a hord can bootstrap its understanding of Hoard's concepts by querying the glossary cards — no external documentation format required.

**For the system:** Every glossary card is a node in the knowledge graph. It has incoming links (documents and cards that reference it) and outgoing links (related concepts). The documentation scaffold grows with the system. New concepts get cards. New cards get relations. The scaffold becomes richer over time without any document needing to be rewritten.

## Provenance

The contextual scaffold concept synthesizes three traditions:

- **Library science:** The catalog is the scaffold for the collection. It bears the organizational weight so that the books can simply be books.

- **Hypertext:** Ted Nelson's vision of a docuverse where every document is linked to its references, and the references are themselves documents. The web partly realized this; Hoard's card network realizes it more fully.

- **Literate programming:** Knuth's insight that programs should be written as literature, with code and documentation interwoven. Hoard extends this to knowledge: the documentation and the knowledge graph are interwoven, expressed in the same format, maintained by the same tools.

The specific insight — that the scaffold should be invisible until needed, that it should bear load permanently rather than temporarily, and that it should be built from the same material as the structure it supports — is original to this project. It follows from the homoiconicity principle: if metadata is data, then documentation is knowledge, and both belong in the same graph.
