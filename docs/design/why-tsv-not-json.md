# Why TSV, Not JSON

**Decision:** Quads are stored as tab-separated values in plain text files, not as JSON, SQLite, or any structured format.

## Context

The quad store is the compiled metadata layer. It needs to be read by: the `hord` CLI, the MCP server, Emacs (hord.el), the web interface, and potentially any tool that wants to work with a hord. The storage format determines the integration cost for every new consumer.

## Options Considered

1. **JSON** — universally supported, self-describing, easy to parse in any language.

2. **SQLite** — fast queries, ACID transactions, standard SQL interface. Single file.

3. **RDF/Turtle/N-Quads** — standard semantic web formats. Rich ecosystem of tools (SPARQL, triple stores).

4. **TSV** — tab-separated values. One quad per line, four fields.

## Why This One

TSV has one property that trumps everything else: **it works with tools that already exist on every Unix system.**

```bash
# Find all broader-term relationships
grep "v:bt" .hord/quads/c348/*.tsv

# Count quads per entity
wc -l .hord/quads/*/*.tsv

# Diff metadata between commits
git diff HEAD~1 -- .hord/quads/

# Extract all titles
grep "v:title" .hord/overlays/strata/quads/*/*.tsv | cut -f3
```

None of these require installing anything. No parser, no library, no runtime. A developer who has never heard of Hoard can understand the format by looking at one file for three seconds.

Git diffs are clean and meaningful. Each line is one assertion. Add a relationship and the diff shows one added line. Change a title and the diff shows one changed line. JSON and SQLite diffs are either unreadable or impossible.

## Tradeoffs Accepted

- **No schema enforcement.** TSV files can contain anything. A malformed line is a silent corruption. The compiler validates on write, but nothing prevents manual edits from introducing bad data. This is mitigated by the fact that quads are derived data — recompile from source files to fix corruption.

- **No query optimization.** Finding all entities of a given type requires scanning all quad files. The UUID-sharded directory structure helps (you only read one file per entity), but there's no index. For the current scale (~40,000 quads), this is fast enough. At millions of quads it would need an index layer.

- **No transactions.** Writing quads is not atomic. A crash mid-compile could leave partial files. Git recovers from this (reset to last commit), but it's not as clean as SQLite's ACID guarantees.

- **Verbose.** The same UUID appears as subject in every quad for an entity. A JSON object would group them. TSV repeats the subject on every line. This costs disk space (trivial) and scan time (negligible at current scale) in exchange for line-level grep and diff.

## Provenance

The choice follows the Unix philosophy: store data in flat text files, use existing tools to process them. It also follows the Git philosophy: human-readable diffs are a feature, not an accident. The specific format (four tab-separated columns) echoes N-Quads (the W3C standard for serializing RDF quads) but deliberately avoids the URI syntax overhead that makes N-Quads hostile to casual inspection.
