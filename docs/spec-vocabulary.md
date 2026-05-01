# Hoard Vocabulary Specification

Version 0.1 -- 2026-05-01

This specification defines Hoard's vocabulary system: how controlled
terms are declared, how they are organized into namespaces, and how
implementors extend them. The vocabulary is the predicate dictionary
that all of Hoard's plumbing depends on. Every relationship expressed
in a quad file, every entity type classification, and every thesaurus
link uses a vocabulary term ID as its canonical identifier.

## 1. Overview

Hoard stores knowledge as quad files -- tab-separated records of the
form `subject predicate object context`. The predicate column must
contain a vocabulary term ID, never a free-text string. This is what
makes the data queryable, mergeable, and portable between hords.

A controlled vocabulary serves three purposes:

1. **Consistency.** Two hords that both use `v:bt` mean the same thing
   by "broader term." There is no ambiguity about whether "BT,"
   "broader," or "parent" was intended.

2. **Rename safety.** Because quads store the term ID (`v:bt`), not
   the human-readable label (`BT`), an implementor can change the
   display label at any time without invalidating existing data.

3. **Extensibility.** A hord can define its own terms alongside the
   shipped defaults. New predicates and entity types are added by
   appending rows to a TSV file, not by modifying source code.

The vocabulary is loaded at compile time. When `hord compile` runs, it
reads the hord's `.hord/vocab/terms.tsv`, resolves every predicate
label (e.g., `BT`) to its term ID (e.g., `v:bt`), and writes quads
using those IDs. Downstream tools -- the MCP server, query commands,
export pipelines -- read the same vocabulary to translate IDs back to
human-readable labels for display.


## 2. terms.tsv Format

The vocabulary is stored in `terms.tsv`, a tab-separated file with
three columns:

```
id	label	scope_note
```

**id** -- The canonical term identifier. This is the string stored in
quad files. It uses a namespace prefix (see Section 4). Examples:
`v:bt`, `wh:con`, `v:s-wo`.

**label** -- A short human-readable label. This is what porcelain
commands display to users. Examples: `BT`, `Concept`,
`strata:isWholeOf`.

**scope_note** -- A prose description of what the term means and when
to use it. This field may be empty but the column must still be
present.

### Rules

- Lines beginning with `#` are comments and are ignored by the parser.
- The header line `id<TAB>label<TAB>scope_note` is required and is
  skipped during parsing.
- A line with only two tab-separated fields is accepted; the scope
  note defaults to an empty string.
- Term IDs must be unique within a single terms.tsv file.
- Term IDs are case-sensitive. `v:bt` and `v:BT` are different terms.
  By convention, all shipped IDs use lowercase.

### Example

The following is an excerpt from the shipped `terms.tsv`:

```
id	label	scope_note
v:bt	BT	Broader term (ANSI/NISO Z39.19)
v:btg	BTG	Broader term (generic, is-a-kind-of)
v:nt	NT	Narrower term
v:rt	RT	Related term
v:uf	UF	Used for (non-preferred term)
v:type	TYPE	Entity type classification
v:title	TITLE	Display title of the entity
v:s-wo	strata:isWholeOf	Strata: entity is a Whole
wh:con	Concept	Word-hord: concept record
wh:wrk	Work	Word-hord: bibliographic work record
```


## 3. relations.tsv Format

The file `relations.tsv` describes relationships *between vocabulary
terms themselves*. It does not describe relationships between entities
in the hord -- those are stored in quad files. `relations.tsv`
captures the internal structure of the vocabulary: which terms are
subtypes of other terms, which terms are inverses of each other.

The format is four tab-separated columns:

```
subject	predicate	object	note
```

**subject** -- A term ID from terms.tsv.

**predicate** -- A term ID expressing the relationship. The shipped
file uses `v:rt` (related term) and `v:bt` (broader term) here.

**object** -- The target term ID.

**note** -- A prose explanation of the relationship.

### Example

```
subject	predicate	object	note
v:bt	v:rt	v:nt	BT and NT are inverse thesaurus relations
v:btg	v:bt	v:bt	BTG is a subtype of BT (generic)
v:bti	v:bt	v:bt	BTI is a subtype of BT (instance)
v:btp	v:bt	v:bt	BTP is a subtype of BT (partitive)
v:uf	v:rt	v:use	UF and USE are inverse preference relations
```

This tells tooling that `v:btg` is a narrower (more specific) form of
`v:bt`, and that `v:bt` and `v:nt` are inverses. An implementation
could use this to infer that if entity A has `v:bt` pointing to entity
B, then entity B implicitly has `v:nt` pointing to entity A.

The relations file is currently informational. The compiler does not
use it during compilation. Future versions of Hoard may use it for
inference and validation.


## 4. Namespaces

Term IDs use a prefix namespace separated by a colon. The shipped
vocabulary defines three namespaces:

### v: -- Structural predicates

Terms in the `v:` namespace are predicates -- they appear in the
predicate column of quad files. They describe relationships between
entities, assign types, and carry metadata.

Examples: `v:bt`, `v:nt`, `v:rt`, `v:type`, `v:title`, `v:author`.

These predicates derive from the ANSI/NISO Z39.19 thesaurus standard
and are supplemented with predicates for Hoard-specific metadata
(type, title, author).

### v:s- -- Strata predicates

A sub-namespace of `v:` for predicates that express Strata
relationships. Strata is Hoard's generalized FRBR model, which
decomposes bibliographic identity into four levels: Whole, Expression,
Manifestation, and Instance.

| Term ID    | Label                     | Meaning                                      |
|------------|---------------------------|----------------------------------------------|
| `v:s-wo`   | `strata:isWholeOf`        | The entity is a Whole (an abstract work)      |
| `v:s-eo`   | `strata:isExpressionOf`   | The entity is an Expression of a Whole        |
| `v:s-mo`   | `strata:isManifestationOf`| The entity is a Manifestation of an Expression|
| `v:s-io`   | `strata:isInstanceOf`     | The entity is an Instance of a Manifestation  |
| `v:s-type` | `strata:entityType`       | Strata-level type classification              |

These predicates link entities across WEMI levels. They are used in
the object column to point to the UUID of the parent entity in the
Strata hierarchy.

### wh: -- Entity types

Terms in the `wh:` namespace are entity type classifiers. They appear
in the object column of quads whose predicate is `v:type`. They
describe *what kind of thing* an entity is.

| Term ID  | Label        | Purpose                                           |
|----------|--------------|---------------------------------------------------|
| `wh:con` | Concept      | A concept record (ideas, definitions, principles)  |
| `wh:pat` | Pattern      | A proto-pattern record (recurring structures)      |
| `wh:key` | Keystone     | A keystone/expression record                       |
| `wh:wrk` | Work         | A bibliographic work record (books, papers, etc.)  |
| `wh:per` | Person       | A person or named entity                           |
| `wh:cat` | Category     | A category or top-term record                      |
| `wh:sys` | System       | A system or meta record                            |
| `wh:pla` | Place        | A place record                                     |
| `wh:evt` | Event        | An event record                                    |
| `wh:obj` | Object       | A physical or digital object                       |
| `wh:org` | Organization | An organization record                             |
| `wh:cap` | Capture      | A capture card (quick notes, fleeting thoughts)    |

An entity's type is recorded as a quad:

```
d4e5f6a7-1001-4000-8000-000000000011	v:type	wh:con	38cbc45a...
```

This says: entity `d4e5f6a7-...` is of type `wh:con` (Concept).


## 5. Built-in Terms Reference

The complete shipped vocabulary as of version 0.1:

### Thesaurus predicates (ANSI/NISO Z39.19)

| ID       | Label | Scope note                              |
|----------|-------|-----------------------------------------|
| `v:bt`   | BT    | Broader term (ANSI/NISO Z39.19)         |
| `v:btg`  | BTG   | Broader term (generic, is-a-kind-of)    |
| `v:bti`  | BTI   | Broader term (instance, is-an-instance-of) |
| `v:btp`  | BTP   | Broader term (partitive, is-part-of)    |
| `v:nt`   | NT    | Narrower term                           |
| `v:ntg`  | NTG   | Narrower term (generic)                 |
| `v:nti`  | NTI   | Narrower term (instance)                |
| `v:ntp`  | NTP   | Narrower term (partitive)               |
| `v:rt`   | RT    | Related term                            |
| `v:uf`   | UF    | Used for (non-preferred term)           |
| `v:use`  | USE   | Preferred term (inverse of UF)          |
| `v:tt`   | TT    | Top term in thesaurus hierarchy         |
| `v:pt`   | PT    | Preferred term (self-reference, display label) |

### Metadata predicates

| ID         | Label  | Scope note                    |
|------------|--------|-------------------------------|
| `v:type`   | TYPE   | Entity type classification    |
| `v:title`  | TITLE  | Display title of the entity   |
| `v:author` | AUTHOR | Author or creator of a work   |

### Strata predicates

| ID         | Label                      | Scope note                                        |
|------------|----------------------------|---------------------------------------------------|
| `v:s-wo`   | strata:isWholeOf           | Strata: entity is a Whole                         |
| `v:s-eo`   | strata:isExpressionOf      | Strata: is an Expression of a Whole               |
| `v:s-mo`   | strata:isManifestationOf   | Strata: is a Manifestation of an Expression       |
| `v:s-io`   | strata:isInstanceOf        | Strata: is an Instance of a Manifestation         |
| `v:s-type` | strata:entityType          | Strata: entity type classification                |

### Entity types

| ID       | Label        | Scope note                                             |
|----------|--------------|--------------------------------------------------------|
| `wh:con` | Concept      | Word-hord: concept record                              |
| `wh:pat` | Pattern      | Word-hord: proto-pattern record                        |
| `wh:key` | Keystone     | Word-hord: keystone/expression record                  |
| `wh:wrk` | Work         | Word-hord: bibliographic work record                   |
| `wh:per` | Person       | Word-hord: person/named entity record                  |
| `wh:cat` | Category     | Word-hord: category/top term record                    |
| `wh:sys` | System       | Word-hord: system/meta record                          |
| `wh:pla` | Place        | Word-hord: place record                                |
| `wh:evt` | Event        | Word-hord: event record                                |
| `wh:obj` | Object       | Word-hord: object record                               |
| `wh:org` | Organization | Word-hord: organization record                         |
| `wh:cap` | Capture      | Word-hord: capture card (quick notes, observations)    |


## 6. How to Add New Terms

Adding a term to the vocabulary is a single-file edit. Open your
hord's `.hord/vocab/terms.tsv` and append a row.

### Step by step

1. **Choose a namespace prefix.** Use `v:` for a new predicate, `wh:`
   for a new entity type. If neither fits, define a new namespace
   prefix (see below).

2. **Choose a term ID.** The ID must be unique within the file. Keep
   it short -- three or four characters after the prefix. Use
   lowercase. Examples: `v:doi`, `wh:mat` (for material).

3. **Choose a label.** This is the human-facing display string.
   It can be changed later without breaking anything.

4. **Write a scope note.** Explain when to use this term and how it
   differs from similar terms. The scope note is documentation; treat
   it as such.

5. **Append the row to terms.tsv:**

   ```
   v:doi	DOI	Digital Object Identifier for a work
   ```

6. **If the new term has vocabulary-level relationships** (it is a
   subtype of another term, or it is the inverse of another term),
   add a row to `relations.tsv`:

   ```
   v:doi	v:bt	v:type	DOI is a subtype of TYPE (a more specific identifier)
   ```

7. **Run `hord compile`** to verify the vocabulary loads without
   errors.

### Example: adding a "Dataset" entity type

Suppose you want to classify entities as datasets. Add to
`.hord/vocab/terms.tsv`:

```
wh:dat	Dataset	A structured dataset (CSV, database export, etc.)
```

Then in your org or markdown files, set the entity type to `wh:dat`.
The compiler will emit a quad:

```
<uuid>	v:type	wh:dat	<blob-hash>
```


## 7. How to Add New Entity Types

Entity types live in the `wh:` namespace. The process is identical to
Section 6, with one additional constraint: the term ID must use the
`wh:` prefix, and it must be a noun that describes a class of things.

### Conventions

- The ID after `wh:` should be three lowercase letters. This is not
  enforced by the parser but is the convention used by all shipped
  types (`wh:con`, `wh:pat`, `wh:wrk`, etc.).

- The label should be a singular noun in title case: `Concept`, not
  `concepts` or `CONCEPT`.

- The scope note should begin with the namespace context. All shipped
  types begin with `Word-hord:` to indicate they originate from the
  word-hord entity model.

### Checking your work

After adding a type, verify it by running the MCP `vocab_lookup` tool
or the CLI equivalent:

```
$ hord vocab-lookup wh:dat
wh:dat
  Label: Dataset
  Scope: A structured dataset (CSV, database export, etc.)
```


## 8. How to Add New Predicates

Predicates live in the `v:` namespace (or `v:s-` for Strata
predicates). Adding a predicate to `terms.tsv` makes it available for
vocabulary lookup and display. To make the compiler *recognize* the
predicate when parsing source files, a second step is required.

### Step 1: Add to terms.tsv

```
v:src	SOURCE	Source URL or location of the entity
```

### Step 2: Register in the compiler's REL_TO_PREDICATE map

The compiler (`compile.py`) uses a dictionary called
`REL_TO_PREDICATE` to map short relation labels found in source files
to vocabulary term IDs. If you want authors to write `SRC` in their
org-mode relation drawers and have it compile to `v:src`, add an entry:

```python
REL_TO_PREDICATE = {
    ...
    "SRC": "v:src",
}
```

Without this mapping, the compiler will emit a warning ("unknown
relation type") and skip the relation. The vocabulary term will still
exist and can be used by tools that write quads directly (such as MCP
tools or import scripts), but the org/markdown compilation pipeline
will not produce it.

### Step 3: Add to relations.tsv (if applicable)

If the new predicate has an inverse or is a subtype of an existing
predicate, record that in `relations.tsv`. For example, if `v:src` is
a more specific form of a general "reference" predicate:

```
v:src	v:bt	v:rt	SOURCE is a specialized form of related-term reference
```

### Strata predicates

Strata predicates follow the same process but use the `v:s-` prefix.
The compiler maps Strata labels differently -- the short forms `WO`,
`EO`, `MO`, `IO` are mapped in `REL_TO_PREDICATE`:

```python
"WO": "v:s-wo",
"EO": "v:s-eo",
"MO": "v:s-mo",
"IO": "v:s-io",
```

### Hard-coded predicates

Three predicates -- `v:type`, `v:title`, and `v:author` -- are
emitted directly by the compiler without going through
`REL_TO_PREDICATE`. They are extracted from structured metadata fields
(the `#+TYPE:` header, the document title, the `#+AUTHOR:` header)
rather than from relation drawers. To add a new metadata-level
predicate of this kind requires modifying the compiler's record
processing loop.


## 9. Vocabulary as Plumbing

The vocabulary system is plumbing, not porcelain. This distinction
matters for implementors.

**Plumbing** uses term IDs. Quad files contain `v:bt`, never
`Broader term`. The `Vocabulary.lookup()` method takes a term ID and
returns a `Term` object. The `Vocabulary.is_valid()` method validates
term IDs.

**Porcelain** displays labels. When a user-facing tool needs to show a
relationship to a human, it calls `Vocabulary.label(term_id)` to
translate `v:bt` to `BT`. If the term ID is not found in the
vocabulary, the raw ID is returned as a fallback -- the system
degrades gracefully rather than failing.

This separation means:

- Quad files are stable across label renames. If you decide `BT`
  should display as `Broader` instead, change the label column in
  terms.tsv. No quad files need updating.

- Quad files are portable between hords. Two hords that share the
  same term IDs can merge their quads directly.

- Unknown term IDs do not crash the system. A quad with predicate
  `x:custom` will pass through the pipeline. Porcelain will display
  the raw ID `x:custom` until the term is added to the vocabulary.

### Vocabulary loading

The vocabulary is loaded by `Vocabulary.load(terms_path)`, which reads
`terms.tsv` and builds an in-memory dictionary keyed by term ID. The
`find_vocab()` function locates the vocabulary file at
`.hord/vocab/terms.tsv` relative to the hord root.

When `hord init` creates a new hord, it copies the default vocabulary
files (both `terms.tsv` and `relations.tsv`) from the installed
package into `.hord/vocab/`. From that point on, the hord's vocabulary
is independent -- edits to the hord's copy do not affect the package
defaults, and package upgrades do not overwrite the hord's vocabulary.

### The Vocabulary class

```python
class Vocabulary:
    def load(cls, terms_path: str) -> Vocabulary
    def lookup(self, term_id: str) -> Term | None
    def label(self, term_id: str) -> str
    def is_valid(self, term_id: str) -> bool
    def all_terms(self) -> list[Term]
```

`Term` is a dataclass with three fields: `id`, `label`, `scope_note`.


## 10. Design Rationale

### Why TSV, not RDF/OWL/SKOS?

Hoard's vocabulary could be expressed in RDF using SKOS (Simple
Knowledge Organization System). The thesaurus relations (`BT`, `NT`,
`RT`, `UF`) map directly to SKOS properties (`skos:broader`,
`skos:narrower`, `skos:related`, `skos:altLabel`). There are good
reasons we do not use SKOS or any RDF serialization:

1. **Tooling overhead.** Parsing RDF requires an RDF library. Parsing
   TSV requires splitting on tabs. Hoard is designed to work with
   minimal dependencies and to be debuggable with standard Unix tools
   (`cut`, `sort`, `grep`, `awk`).

2. **Human readability.** A TSV file can be read and edited in any
   text editor. An RDF/XML or Turtle file requires understanding RDF
   syntax. The vocabulary is meant to be edited by the hord's owner,
   not by a specialist.

3. **Git friendliness.** TSV files produce clean, line-oriented diffs.
   RDF serializations (particularly RDF/XML) produce noisy diffs that
   obscure the actual change.

4. **Sufficiency.** The vocabulary is a flat list of terms with
   optional relationships. It does not need inference, reasoning, or
   ontological class hierarchies. TSV is sufficient for the data model.

If a future use case requires interoperability with RDF/SKOS systems,
the mapping is straightforward: `v:bt` maps to `skos:broader`, `v:uf`
maps to `skos:altLabel`, and so on. An export tool can generate SKOS
from `terms.tsv` and `relations.tsv` without changing the source
format.

### Why flat files, not a database?

The vocabulary is loaded into memory once at startup. The shipped
vocabulary contains 34 terms. Even a heavily extended vocabulary is
unlikely to exceed a few hundred terms. A database would add
complexity (schema migrations, connection management, transactions)
without adding value. The flat file is the database.

### Why rename-safe?

The separation between term IDs and labels is a deliberate design
choice. In systems that use human-readable strings as identifiers
(e.g., storing "Broader term" directly in data records), renaming a
label requires updating every record that references it. In Hoard,
labels are display-only. The ID `v:bt` is the stable identifier. The
label `BT` can be changed to `Broader`, `Broader Term`, or the
Japanese equivalent without touching a single quad file.

This also means that labels do not need to be unique. Two terms may
share the same label (though this would be confusing for users and is
not recommended). IDs must be unique.

### Why per-hord vocabulary?

Each hord gets its own copy of the vocabulary at `hord init` time.
This has two consequences:

1. **Independence.** A hord can add domain-specific terms without
   affecting other hords. A hord focused on music might add `wh:alb`
   (Album), `wh:trk` (Track), and `v:perf` (performed by). These
   terms are meaningful within that hord and irrelevant to others.

2. **Stability.** Upgrading the Hoard package does not change an
   existing hord's vocabulary. If a new version of Hoard ships
   additional terms, the hord owner can merge them manually. This
   prevents surprises where a package upgrade changes the meaning of
   an existing term.

### Namespace conventions

The namespace prefix convention (`v:`, `wh:`) is a naming convention,
not a technical enforcement mechanism. The parser does not validate
prefixes. An implementor could define terms with any prefix (`music:`,
`geo:`, `bio:`). The convention exists so that term IDs are
self-documenting: seeing `v:bt` in a quad file immediately tells you
it is a structural predicate, while `wh:con` tells you it is an
entity type.

Implementors who define custom namespaces should choose a prefix that
does not collide with the shipped namespaces (`v:` and `wh:`).
