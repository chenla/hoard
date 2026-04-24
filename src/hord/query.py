"""hord query — look up entities and their relationships."""

import os

import click

from hord.git_utils import find_hord_root
from hord.quad import read_quads, quad_path, Quad
from hord.vocab import Vocabulary, find_vocab


def load_index(hord_root: str) -> dict[str, str]:
    """Load index.tsv into a dict: path → uuid and name → uuid."""
    index = {}
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if not os.path.exists(index_path):
        return index
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                path, uuid = parts[0], parts[1]
                index[path] = uuid
                index[uuid] = uuid
                # Also index by filename without extension
                basename = os.path.splitext(os.path.basename(path))[0]
                index[basename] = uuid
    return index


def find_incoming(hord_root: str, target_uuid: str) -> list[Quad]:
    """Find all quads where the object is the target UUID."""
    incoming = []
    quads_dir = os.path.join(hord_root, ".hord", "quads")
    if not os.path.exists(quads_dir):
        return incoming
    for prefix_dir in os.listdir(quads_dir):
        prefix_path = os.path.join(quads_dir, prefix_dir)
        if not os.path.isdir(prefix_path):
            continue
        for fname in os.listdir(prefix_path):
            if not fname.endswith(".tsv"):
                continue
            fpath = os.path.join(prefix_path, fname)
            for q in read_quads(fpath):
                if q.object == target_uuid:
                    incoming.append(q)
    return incoming


def resolve_uuid_label(hord_root: str, uuid: str, vocab: Vocabulary | None) -> str:
    """Try to find a human-readable label for a UUID."""
    qpath = quad_path(hord_root, uuid)
    for q in read_quads(qpath):
        if q.predicate == "v:title":
            return q.object
    return uuid


@click.command("query")
@click.argument("term")
@click.option("--format", "fmt", type=click.Choice(["human", "tsv"]),
              default="human", help="Output format")
def query_cmd(term, fmt):
    """Look up an entity by UUID, filename, or path.

    Shows all quads for the entity and all incoming links
    (quads where this entity appears as the object).
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    # Load index and resolve term to UUID
    index = load_index(hord_root)
    uuid = index.get(term)

    # Try partial UUID match
    if uuid is None:
        for key, val in index.items():
            if key.startswith(term) and len(term) >= 4:
                uuid = val
                break

    if uuid is None:
        click.echo(f"Not found: {term}", err=True)
        click.echo("Try a UUID, filename (without .org), or path.", err=True)
        raise SystemExit(1)

    # Load vocabulary
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    # Read quads for this entity
    qpath = quad_path(hord_root, uuid)
    quads = read_quads(qpath)

    if fmt == "tsv":
        for q in quads:
            click.echo(q.to_tsv())
        return

    # Human-readable output
    # Find title
    title = None
    for q in quads:
        if q.predicate == "v:title":
            title = q.object
            break

    click.echo(f"{'═' * 60}")
    if title:
        click.echo(f"  {title}")
    click.echo(f"  {uuid}")
    click.echo(f"{'═' * 60}")

    # Separate quads into structural and strata
    strata_predicates = {"v:s-wo", "v:s-eo", "v:s-mo", "v:s-io", "v:s-type"}
    structural_quads = []
    strata_quads = []
    for q in quads:
        if q.predicate == "v:title":
            continue  # Already shown in header
        if q.predicate in strata_predicates:
            strata_quads.append(q)
        else:
            structural_quads.append(q)

    # Display structural relationships
    click.echo()
    for q in structural_quads:
        pred_label = vocab.label(q.predicate) if vocab else q.predicate
        obj_display = q.object
        if _looks_like_uuid(q.object):
            resolved = resolve_uuid_label(hord_root, q.object, vocab)
            if resolved != q.object:
                obj_display = f"{resolved}  ({q.object[:8]}…)"
        click.echo(f"  {pred_label:>12}  {obj_display}")

    # Display strata (WEMI) relationships
    if strata_quads:
        click.echo()
        click.echo(f"{'─' * 60}")
        click.echo("  Strata (WEMI):")
        click.echo()
        for q in strata_quads:
            pred_label = vocab.label(q.predicate) if vocab else q.predicate
            obj_display = q.object
            if _looks_like_uuid(q.object):
                resolved = resolve_uuid_label(hord_root, q.object, vocab)
                if resolved != q.object:
                    obj_display = f"{resolved}  ({q.object[:8]}…)"
            click.echo(f"  {pred_label:>20}  {obj_display}")

    # Find incoming links
    incoming = find_incoming(hord_root, uuid)
    if incoming:
        click.echo()
        click.echo(f"{'─' * 60}")
        click.echo("  Incoming links:")
        click.echo()
        for q in incoming:
            pred_label = vocab.label(q.predicate) if vocab else q.predicate
            subj_label = resolve_uuid_label(hord_root, q.subject, vocab)
            if subj_label != q.subject:
                subj_display = f"{subj_label}  ({q.subject[:8]}…)"
            else:
                subj_display = q.subject
            click.echo(f"  {subj_display}")
            click.echo(f"    ← {pred_label}")

    click.echo()


def _looks_like_uuid(s: str) -> bool:
    """Quick check if a string looks like a UUID."""
    return len(s) == 36 and s.count("-") == 4
