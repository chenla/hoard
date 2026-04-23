# Why Hoard: What Library Science Already Solved That AI Knowledge Tools Are Rediscovering Badly

*Ford Collins — April 2026*

---

A few weeks ago, Andrej Karpathy published a short document that over 100,000 people bookmarked. The idea was almost too simple: instead of asking AI questions and throwing away the answers, have the AI build and maintain a persistent wiki — a structured set of notes that gets richer every time you feed it a new source. The AI does the cross-referencing, the filing, the maintenance that humans abandon. Your knowledge compounds instead of evaporating.

He called it "LLM Wiki." His key sentence: *"The knowledge is compiled once and then kept current, not re-derived on every query."*

That sentence matters. Most AI knowledge tools — ChatGPT file uploads, NotebookLM, RAG systems — re-derive understanding from scratch on every question. Karpathy's insight is that the AI should write down what it learns, so the next question builds on the last one instead of starting over.

He's right. And the 100,000 bookmarks suggest people have been waiting for someone to say this clearly. But the solution he proposed has a structural problem that almost nobody in those bookmarks is thinking about yet — and it's the same problem that library science identified and solved decades ago.

## The Problem Behind the Problem

Nate Jones, who built a competing system called Open Brain, wrote a thoughtful response identifying the core architectural fork: does the AI do the hard thinking when information arrives (write-time, Karpathy's approach), or when you ask about it (query-time, Jones's approach)? His analysis is the clearest framing of this tradeoff I've seen.

But both approaches share three gaps that neither addresses:

### 1. The Identity Problem

When Karpathy's wiki mentions "Kanban" on five different pages, there's nothing connecting those references except the string "Kanban." Rename it to "Pull System" on one page and the connection breaks silently. There is no concept of *what something is* independent of what it's called.

This is the problem that authority records solve in library science. Every concept, person, place, or work gets a permanent identifier — a UUID, a Library of Congress control number, an ORCID. The identifier is the stable peg; names are just labels that hang from it. Labels change, identifiers don't.

In Hoard, every entity has a UUID assigned at creation. The concept "Kanban" is `d4e5f6a7-1001-4000-8000-000000000011`. It's also 看板, also "signboard system," also "pull scheduling." These are all `UF` (Used For) entries pointing at the same identity. Rename any label, the identity is untouched. Every relationship in the system points to UUIDs, not strings.

### 2. The Vocabulary Problem

When an AI maintains a wiki, it makes word choices. On Monday it writes "machine learning." On Wednesday, processing a different source, it writes "ML." On Friday, "statistical learning." To a human reader these look like normal variation. To the knowledge structure, they're three unconnected concepts.

This is the problem that controlled vocabularies solve. ANSI/NISO Z39.19 (the standard for thesaurus construction) defines a system of term relationships that has been in production use for over fifty years:

- **BT** (Broader Term): Kanban → Toyota Production System
- **NT** (Narrower Term): Toyota Production System → Kanban
- **RT** (Related Term): Kanban ↔ Just-in-Time Manufacturing
- **UF** (Used For): Kanban ← 看板, Pull System, Signboard
- **USE** (Preferred Term): 看板 → Kanban

In Karpathy's wiki, these relationships are implicit in prose — the AI might write "Kanban, a component of the Toyota Production System, is related to Just-in-Time Manufacturing." That sentence encodes a BT, an RT, and a UF, but they're trapped in natural language where no machine (including the AI itself in a future session) can reliably extract them.

In Hoard, every relationship is a typed quad:

```
d4e5f6a7…   v:bt    c348132e…   a1b2c3d4…
```

That's the subject (Kanban's UUID), predicate (a vocabulary term ID for "broader term"), object (TPS's UUID), and context (the git blob hash of the source file for provenance). Four fields. Grep-friendly. Git-diffable. Unambiguous.

The predicates themselves are vocabulary term IDs, not raw strings. `v:bt` means "broader term" because `vocab/terms.tsv` says so. Rename the label, the quads are untouched. Split a term into subtypes, old quads remain valid. The indirection is the point.

### 3. The Provenance Problem

Jones identified the most dangerous failure mode of wikis: **confident prose that's quietly wrong.** A wiki page reads with authority even when its underlying information is stale. A database with gaps looks ignorant — you can see what's missing. A wiki with stale synthesis looks knowledgeable — you can't see what's wrong. Jones calls this "wiki drift."

His solution is to use a database as the single source of truth and generate the wiki from it. That's half right. The missing half is *provenance at the claim level*.

In Hoard, every quad has a context column containing the git blob hash of the source file at the time the quad was generated. This means:

- Every metadata claim is traceable to a specific version of a specific file
- `hord status` compares stored hashes against current file hashes and reports exactly which entities have stale metadata
- Staleness is visible and quantifiable, not hidden behind confident prose

```bash
$ hord status
Stale (1):
  ✗ content/Kanban--4.org  (content changed)

1 issue(s). Run 'hord compile' to update.
```

This is not a feature bolted onto a wiki. It's a structural property of the storage format.

## This Isn't New

None of these ideas are original. Authority records, controlled vocabularies, and provenance tracking are foundational concepts in library science and knowledge engineering. MARC records have had authority control since the 1970s. The Dublin Core metadata standard dates to 1995. FRBR (Functional Requirements for Bibliographic Records) formalized the distinction between a work, its expressions, its manifestations, and its instances in 1998.

These systems work. They're in production in every major library system in the world. But they didn't survive the transition to personal knowledge management because they require *relentless human maintenance*. Cataloging a single book properly — assigning subject headings, creating authority records, establishing relationships — takes trained librarians minutes per item. Nobody does that for their personal notes.

AI changes that equation. The maintenance that makes controlled vocabularies and authority records practical is exactly the kind of tedious, systematic, high-volume work that AI handles well. The same insight Karpathy had — "the AI does the grunt work, you do the judgment work" — applies with even more force to structured metadata than to prose wikis.

Hoard is built on this premise: take the structural principles that librarians proved work at scale, strip away the parts that required manual maintenance, and build tooling where AI agents can do the structural work while humans provide judgment and direction.

## Territory and Map

Hoard's core architectural principle is the separation of territory and map.

**Territory** is your content — org-mode files, markdown documents, whatever you write. These live in a git repository, version-controlled as always. Hoard never modifies your content.

**Map** is the metadata — the quads, the vocabulary, the index. These live in a `.hord/` directory alongside `.git/`. The map describes the territory but cannot corrupt it. A bad map is recoverable (recompile from the territory). A bad territory is the author's problem, not the metadata system's.

```
myrepo/
├── .git/           # version control (standard git)
├── .hord/          # metadata overlay (Hoard)
│   ├── config.toml
│   ├── index.tsv   # path ↔ UUID mapping
│   ├── vocab/      # controlled vocabulary
│   └── quads/      # semantic metadata (TSV)
└── content/        # your files (the territory)
```

This separation has consequences:

1. **Format independence.** Hoard works with org-mode, markdown, or any text format. The `hord compile` command parses your content files and extracts metadata into quads. The `hord convert` command translates between org-mode and markdown, preserving all metadata. Both formats produce identical quads.

2. **Non-destructive metadata.** Unlike inline tags or wiki links, Hoard's metadata is stored separately from the content it describes. You can delete the entire `.hord/` directory and your content is untouched. You can recompile the metadata at any time from the source files.

3. **Git-native.** The `.hord/` directory is just files in a git repo. Quads are TSV — one line per statement, four tab-separated fields. Every change to the metadata is a git diff. Every version is recoverable. No special database, no service to run, no binary formats.

## What This Looks Like in Practice

The [Hoard repository](https://github.com/chenla/hoard) includes a working demo: 21 records about the Toyota Production System — concepts (Kanban, Jidoka, Kaizen, Just-in-Time, Muda), people (Taiichi Ohno, Shigeo Shingo, W. Edwards Deming), and bibliographic works.

Query the central concept:

```bash
$ hord query Toyota_Production_System--4

════════════════════════════════════════════════════════════
  Toyota Production System—4
  c348132e-7cdf-438d-9a1f-69d75f382bee
════════════════════════════════════════════════════════════

          TYPE  wh:con
            TT  Concept—8  (852a6e49…)
            BT  Lean Manufacturing—4  (9916ba93…)
            NT  Kanban—4  (d4e5f6a7…)
            NT  Jidoka—4  (d4e5f6a7…)
            NT  Just-in-Time Manufacturing—4  (d4e5f6a7…)
            NT  Kaizen—4  (d4e5f6a7…)
            NT  Muda—4  (d4e5f6a7…)
            RT  Andon—4  (d4e5f6a7…)
            RT  Poka-yoke—4  (d4e5f6a7…)
            RT  Heijunka—4  (d4e5f6a7…)
            RT  Genchi Genbutsu—4  (d4e5f6a7…)
            UF  TPS
            PT  Toyota Production System—4

────────────────────────────────────────────────────────────
  Incoming links:

  Taiichi Ohno—7  (e5f6a7b8…)
    ← RT
  Shigeo Shingo—7  (e5f6a7b8…)
    ← RT
  W. Edwards Deming—7  (e5f6a7b8…)
    ← RT
  Toyota Production System: Beyond Large-Scale Production—6
    ← RT
  The Machine That Changed the World—6
    ← RT
  ...
```

One query shows: the concept's type, its position in the thesaurus hierarchy (BT/NT), its related concepts (RT), its aliases (UF), and every entity in the system that links back to it — people, books, sub-concepts. All resolved from structured quads, not scraped from prose.

A flat wiki can show you a page about the Toyota Production System. It cannot show you, structurally, that Kanban is a *narrower term* of TPS while Andon is a *related term*. It cannot show you that Taiichi Ohno is a *person* who links to TPS through a typed relationship, while "The Machine That Changed the World" is a *bibliographic work* that links to it through a different typed relationship. It cannot show you that 看板 and "Kanban" and "pull scheduling" are all labels for the same identity.

Hoard can, because the structure is in the data, not in the prose.

## The Multilingual Test

One of the sharpest tests of a knowledge system is how it handles equivalent terms across languages. The Toyota Production System is particularly revealing because many of its core concepts are Japanese words that have been adopted into English with varying degrees of translation:

- Kanban = 看板 = signboard system = pull scheduling
- Kaizen = 改善 = continuous improvement
- Jidoka = 自働化 = autonomation = automation with a human touch
- Muda = 無駄 = waste
- Poka-yoke = ポカヨケ = mistake-proofing

In a flat wiki, these might appear as separate pages, inline translations, or parenthetical notes — depending on whatever the AI decided at ingest time. There is no structural way to say "these are all the same concept."

In Hoard, each is a `UF` (Used For) entry pointing at a single UUID. The concept is the identity; the words are labels. Query in any language, arrive at the same entity.

## What Comes Next

Hoard v0.1 is a proof of concept. It demonstrates the core architecture — quads, vocabulary control, identity, provenance — with working tooling and a real dataset. What it doesn't yet have:

**Overlay branches.** The current version stores all metadata on a single branch. The design supports multiple metadata overlays on separate git branches — different maps of the same territory. A *Strata* overlay describing what things are (identity, type, entity relationships). A *Structural* overlay describing how things are organized (thesaurus hierarchies, sequences, groupings). These answer different questions about the same content and can coexist without conflict.

**Cross-hord vocabulary sharing.** Vocabularies can be shared across hords as git submodules, with crosswalk tables mapping between different term sets. This is how the system scales beyond personal use — shared vocabularies enable interoperability between independent knowledge bases without requiring a central authority.

**AI agent integration.** The plumbing is designed for AI/agent use first, human use second. Structured TSV quads are easier for agents to read, validate, and extend than prose wikis. The next step is MCP (Model Context Protocol) integration so any AI tool can read from and write to a hord natively.

The demo dataset, the tooling, and this document are available at [github.com/chenla/hoard](https://github.com/chenla/hoard).

---

*Hoard is named from the Anglo-Saxon "hord" — a store of treasure or knowledge. The word-hord (wordhord) was a poet's collection of words and phrases to draw upon when composing. The modern Hoard is the same idea with better infrastructure.*
