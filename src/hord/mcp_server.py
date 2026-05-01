"""Hoard MCP server — expose hord operations as MCP tools.

Runs as a local stdio server. Add to ~/.claude/settings.json:

{
  "mcpServers": {
    "hoard": {
      "command": "/path/to/hoard/.venv/bin/python",
      "args": ["-m", "hord.mcp_server"],
      "env": {
        "HORD_ROOT": "/path/to/your/hord"
      }
    }
  }
}
"""

import os
import sys

from mcp.server.fastmcp import FastMCP

# Import hord internals
from hord.git_utils import find_hord_root, blob_hash
from hord.org_parser import parse_org_file, scan_directory as scan_org
from hord.md_parser import parse_md_file, scan_directory as scan_md
from hord.quad import (Quad, read_quads, write_quads, quad_path,
                       read_all_quads, overlay_for_predicate, list_overlays)
from hord.vocab import Vocabulary, find_vocab
from hord.query import load_index, find_incoming, resolve_uuid_label
from hord.compile import REL_TO_PREDICATE
from hord.new import TYPE_SHORTCUTS, TYPE_SUFFIX, slugify, scaffold_org, scaffold_md, make_timestamp


def get_hord_root() -> str:
    """Get the hord root from env or current directory."""
    root = os.environ.get("HORD_ROOT")
    if root and os.path.isdir(os.path.join(root, ".hord")):
        return root
    root = find_hord_root(".")
    if root:
        return root
    raise RuntimeError("No hord found. Set HORD_ROOT or run from inside a hord.")


mcp = FastMCP("hoard")


@mcp.tool()
def query(term: str) -> str:
    """Look up an entity by UUID, filename, or partial UUID.

    Returns all quads for the entity with vocabulary labels
    resolved, plus all incoming links (entities that reference
    this one). Use this to explore the knowledge graph.
    """
    hord_root = get_hord_root()
    index = load_index(hord_root)

    # Resolve term to UUID
    uuid = index.get(term)
    if uuid is None:
        for key, val in index.items():
            if key.startswith(term) and len(term) >= 4:
                uuid = val
                break
    if uuid is None:
        return f"Not found: {term}"

    # Load vocab
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    # Read quads (composed across overlays)
    quads = read_all_quads(hord_root, uuid)

    # Build output
    lines = []
    title = None
    for q in quads:
        if q.predicate == "v:title":
            title = q.object

    lines.append(f"Entity: {title or uuid}")
    lines.append(f"UUID: {uuid}")
    lines.append("")

    for q in quads:
        if q.predicate == "v:title":
            continue
        pred_label = vocab.label(q.predicate) if vocab else q.predicate
        obj_display = q.object
        if len(q.object) == 36 and q.object.count("-") == 4:
            resolved = resolve_uuid_label(hord_root, q.object, vocab)
            if resolved != q.object:
                obj_display = f"{resolved} ({q.object[:8]}…)"
        lines.append(f"  {pred_label}: {obj_display}")

    # Incoming links
    incoming = find_incoming(hord_root, uuid)
    if incoming:
        lines.append("")
        lines.append("Incoming links:")
        for q in incoming:
            pred_label = vocab.label(q.predicate) if vocab else q.predicate
            subj_label = resolve_uuid_label(hord_root, q.subject, vocab)
            if subj_label != q.subject:
                lines.append(f"  {subj_label} ({q.subject[:8]}…) ← {pred_label}")
            else:
                lines.append(f"  {q.subject} ← {pred_label}")

    return "\n".join(lines)


@mcp.tool()
def search(text: str) -> str:
    """Search for entities by name or keyword.

    Searches the index for filenames and titles containing
    the search text (case-insensitive). Returns matching
    entities with their UUIDs and types.
    """
    hord_root = get_hord_root()
    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    text_lower = text.lower()
    matches = []
    seen_uuids = set()

    for key, uuid in index.items():
        if uuid in seen_uuids:
            continue
        if text_lower in key.lower():
            seen_uuids.add(uuid)
            title = resolve_uuid_label(hord_root, uuid, vocab)
            # Get type
            entity_type = ""
            for q in read_all_quads(hord_root, uuid):
                if q.predicate == "v:type":
                    entity_type = vocab.label(q.object) if vocab else q.object
                    break
            matches.append(f"  {title}  [{entity_type}]  {uuid}")

    if not matches:
        return f"No entities matching '{text}'"

    return f"Found {len(matches)} entities:\n" + "\n".join(matches)


@mcp.tool()
def list_entities(entity_type: str = "") -> str:
    """List all entities in the hord, optionally filtered by type.

    Type can be a vocab ID (wh:con, wh:per, wh:wrk) or a label
    (Concept, Person, Work). Returns entity names and UUIDs.
    """
    hord_root = get_hord_root()
    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    type_filter = entity_type.lower() if entity_type else ""
    results = []
    seen = set()

    for key, uuid in index.items():
        if uuid in seen:
            continue
        # Only process path-based entries (not duplicate name entries)
        if "/" not in key and uuid != key:
            continue
        seen.add(uuid)

        quads = read_all_quads(hord_root, uuid)

        title = uuid
        etype = ""
        for q in quads:
            if q.predicate == "v:title":
                title = q.object
            elif q.predicate == "v:type":
                etype = q.object

        if type_filter:
            etype_label = vocab.label(etype) if vocab else etype
            if type_filter not in etype.lower() and type_filter not in etype_label.lower():
                continue

        etype_display = vocab.label(etype) if vocab else etype
        results.append(f"  {title}  [{etype_display}]  {uuid}")

    results.sort()
    return f"{len(results)} entities:\n" + "\n".join(results)


@mcp.tool()
def status() -> str:
    """Check which entities have stale metadata.

    Compares git blob hashes stored in quads against current
    file hashes. Reports entities whose content has changed
    since the last compile.
    """
    hord_root = get_hord_root()
    index_path = os.path.join(hord_root, ".hord", "index.tsv")

    if not os.path.exists(index_path):
        return "No index found. Run 'hord compile' first."

    entries = []
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                entries.append((parts[0], parts[1]))

    stale = []
    fresh = 0
    missing = []

    for path, uuid in entries:
        filepath = os.path.join(hord_root, path)
        if not os.path.exists(filepath):
            missing.append(path)
            continue

        try:
            current_hash = blob_hash(filepath)
        except Exception:
            missing.append(path)
            continue

        quads = read_all_quads(hord_root, uuid)
        if not quads:
            stale.append(f"{path} (no quads)")
            continue

        if quads[0].context == current_hash:
            fresh += 1
        else:
            stale.append(f"{path} (content changed)")

    lines = []
    if stale:
        lines.append(f"Stale ({len(stale)}):")
        for s in stale:
            lines.append(f"  ✗ {s}")
    if missing:
        lines.append(f"Missing ({len(missing)}):")
        for m in missing:
            lines.append(f"  ? {m}")
    if not stale and not missing:
        lines.append(f"All {fresh} entities are fresh.")
    else:
        lines.append(f"\n{fresh} fresh, {len(stale)} stale, {len(missing)} missing.")

    return "\n".join(lines)


@mcp.tool()
def compile(path: str = ".") -> str:
    """Compile org/markdown files into Hoard quads.

    Scans the given path for .org and .md files, extracts
    metadata (UUIDs, types, relationships), and writes quad
    files to .hord/quads/. Updates .hord/index.tsv.

    This is a write operation — it modifies .hord/ contents.
    """
    hord_root = get_hord_root()
    scan_path = os.path.join(hord_root, path) if not os.path.isabs(path) else path

    if not os.path.exists(scan_path):
        return f"Path does not exist: {scan_path}"

    # Scan for records
    if os.path.isfile(scan_path):
        if scan_path.endswith(".md"):
            records = [parse_md_file(scan_path)]
        else:
            records = [parse_org_file(scan_path)]
        records = [r for r in records if r.is_valid]
    else:
        records = scan_org(scan_path) + scan_md(scan_path)

    if not records:
        return "No valid records found."

    index_entries = []
    total_quads = 0
    files_compiled = 0

    for record in records:
        if not record.uuid:
            continue

        try:
            context = blob_hash(record.filepath)
        except Exception:
            context = "unknown"

        quads = []

        if record.entity_type:
            quads.append(Quad(record.uuid, "v:type", record.entity_type, context))
        if record.title:
            quads.append(Quad(record.uuid, "v:title", record.title, context))

        for rel in record.relations:
            predicate = REL_TO_PREDICATE.get(rel.rel_type)
            if not predicate:
                continue
            obj = rel.target_uuid if rel.target_uuid else rel.target_label
            quads.append(Quad(record.uuid, predicate, obj, context))

        for alias in record.aliases:
            quads.append(Quad(record.uuid, "v:uf", alias, context))

        # Route quads to overlays (or legacy single dir)
        use_overlays = bool(list_overlays(hord_root))
        if use_overlays:
            overlay_groups: dict[str, list[Quad]] = {}
            for q in quads:
                ov = overlay_for_predicate(q.predicate)
                overlay_groups.setdefault(ov, []).append(q)
            for ov, ov_quads in overlay_groups.items():
                qpath = quad_path(hord_root, record.uuid, overlay=ov)
                write_quads(qpath, ov_quads)
        else:
            qpath = quad_path(hord_root, record.uuid)
            write_quads(qpath, quads)
        total_quads += len(quads)
        files_compiled += 1

        relpath = os.path.relpath(record.filepath, hord_root)
        index_entries.append((relpath, record.uuid))

    # Write index
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    with open(index_path, "w") as f:
        f.write("path\tuuid\n")
        for p, u in sorted(index_entries):
            f.write(f"{p}\t{u}\n")

    return f"Compiled {files_compiled} files → {total_quads} quads, {len(index_entries)} index entries."


@mcp.tool()
def vocab_lookup(term: str = "") -> str:
    """Look up vocabulary terms.

    With no argument, lists all vocabulary terms.
    With a term ID or keyword, shows matching terms
    with their labels and scope notes.
    """
    hord_root = get_hord_root()
    vocab_path = find_vocab(hord_root)
    if not vocab_path:
        return "No vocabulary found."

    vocab = Vocabulary.load(vocab_path)

    if not term:
        lines = ["Vocabulary terms:"]
        for t in vocab.all_terms():
            lines.append(f"  {t.id:16s} {t.label:20s} {t.scope_note}")
        return "\n".join(lines)

    # Exact lookup
    t = vocab.lookup(term)
    if t:
        return f"{t.id}\n  Label: {t.label}\n  Scope: {t.scope_note}"

    # Keyword search
    term_lower = term.lower()
    matches = [t for t in vocab.all_terms()
               if term_lower in t.id.lower()
               or term_lower in t.label.lower()
               or term_lower in t.scope_note.lower()]

    if not matches:
        return f"No vocabulary terms matching '{term}'"

    lines = [f"Found {len(matches)} terms:"]
    for t in matches:
        lines.append(f"  {t.id:16s} {t.label:20s} {t.scope_note}")
    return "\n".join(lines)


@mcp.tool()
def read_content(term: str) -> str:
    """Read the full content of an entity's source file.

    Given a UUID, filename, or partial UUID, returns the
    raw content of the source file (org-mode or markdown).
    Use this when you need the actual text, not just metadata.
    """
    hord_root = get_hord_root()
    index = load_index(hord_root)

    uuid = index.get(term)
    if uuid is None:
        for key, val in index.items():
            if key.startswith(term) and len(term) >= 4:
                uuid = val
                break
    if uuid is None:
        return f"Not found: {term}"

    # Find path from index
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    filepath = None
    with open(index_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and parts[1] == uuid:
                filepath = os.path.join(hord_root, parts[0])
                break

    if not filepath or not os.path.exists(filepath):
        return f"Source file not found for {uuid}"

    with open(filepath, "r") as f:
        return f.read()


@mcp.tool()
def new_card(title: str, entity_type: str = "con", fmt: str = "org",
             content_dir: str = "content", source: str = "") -> str:
    """Create a new card with a UUID and metadata scaffold.

    Creates a properly formatted org-mode or markdown file
    with a unique UUID, type classification, and timestamp.
    Returns the path, UUID, and type of the new card.

    entity_type can be a shortcut (con, per, wrk, pat, cap, etc.)
    or a full vocab ID (wh:con, wh:per, wh:cap, etc.).

    For capture cards (type=cap), defaults to capture/ directory
    and supports a source field (reading, conversation, observation, etc.).
    """
    import uuid as uuid_mod

    hord_root = get_hord_root()

    # Resolve entity type
    etype = entity_type.lower()
    if etype.startswith("wh:"):
        resolved_type = etype
    else:
        resolved_type = TYPE_SHORTCUTS.get(etype)
        if not resolved_type:
            return f"Unknown type '{entity_type}'. Valid: {', '.join(sorted(TYPE_SHORTCUTS.keys()))}"

    # Default capture cards to capture/ directory
    if resolved_type == "wh:cap" and content_dir == "content":
        content_dir = "capture"

    card_uuid = str(uuid_mod.uuid4())
    timestamp = make_timestamp()

    suffix = TYPE_SUFFIX.get(resolved_type, "4")
    slug = slugify(title)
    ext = "org" if fmt == "org" else "md"
    filename = f"{slug}--{suffix}.{ext}"

    out_dir = os.path.join(hord_root, content_dir)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath):
        return f"File already exists: {filepath}"

    if fmt == "org":
        content = scaffold_org(card_uuid, title, resolved_type, timestamp, source)
    else:
        content = scaffold_md(card_uuid, title, resolved_type, timestamp, source)

    with open(filepath, "w") as f:
        f.write(content)

    relpath = os.path.relpath(filepath, hord_root)
    return f"Created {relpath}\n  UUID: {card_uuid}\n  Type: {resolved_type}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
