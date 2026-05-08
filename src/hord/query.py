"""hord query — look up entities and their relationships."""

import os

import click

from hord.git_utils import find_hord_root
from hord.quad import read_quads, quad_path, Quad, read_all_quads, find_all_quads_dirs
from hord.vocab import Vocabulary, find_vocab
from hord.holon import (
    find_expression_for, build_basename_index,
    _get_card_type, _get_card_title,
)


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
    """Find all quads where the object is the target UUID.
    Searches across all overlays (or legacy quads dir)."""
    incoming = []
    for quads_dir in find_all_quads_dirs(hord_root):
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
    for q in read_all_quads(hord_root, uuid):
        if q.predicate == "v:title":
            return q.object
    return uuid


@click.command("query")
@click.argument("term")
@click.option("--format", "fmt", type=click.Choice(["human", "tsv"]),
              default="human", help="Output format")
@click.option("--holon", "holon_term", default=None,
              help="View through a holon's lens (name, slug, or UUID)")
def query_cmd(term, fmt, holon_term):
    """Look up an entity by UUID, filename, or path.

    Shows all quads for the entity and all incoming links
    (quads where this entity appears as the object).

    With --holon, shows the holon's members with expression
    substitution and ordering applied.
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

    # If --holon was given, resolve and display holon view instead
    if holon_term:
        _display_holon_view(hord_root, holon_term, index, vocab, fmt)
        return

    # Read quads for this entity (composed across all overlays)
    quads = read_all_quads(hord_root, uuid)

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


def _display_holon_view(hord_root: str, holon_term: str,
                        index: dict[str, str], vocab, fmt: str) -> None:
    """Display a holon's members with expression substitution and ordering."""
    # Resolve holon term to UUID
    holon_uuid = index.get(holon_term)
    if holon_uuid is None:
        for key, val in index.items():
            if key.startswith(holon_term) and len(holon_term) >= 4:
                holon_uuid = val
                break
    if holon_uuid is None:
        click.echo(f"Holon not found: {holon_term}", err=True)
        raise SystemExit(1)

    # Verify it's a holon
    holon_type = _get_card_type(hord_root, holon_uuid)
    if holon_type != "wh:holon":
        click.echo(f"'{holon_term}' is not a holon (type: {holon_type})", err=True)
        raise SystemExit(1)

    # Read holon quads from structural overlay
    holon_quads = read_all_quads(hord_root, holon_uuid)

    # Extract members, expression preference, and ordering
    members = {}       # uuid → order position
    expr_prefer = None
    holon_title = None
    order_map = {}     # member_uuid → position

    for q in holon_quads:
        if q.predicate == "v:h-member":
            members[q.object] = 999  # default order
        elif q.predicate == "v:h-expr":
            expr_prefer = q.object
        elif q.predicate == "v:title":
            holon_title = q.object
        elif q.predicate == "v:h-order":
            try:
                order_map[q.subject] = int(q.object)
            except ValueError:
                pass

    # Apply ordering
    for member_uuid, pos in order_map.items():
        if member_uuid in members:
            members[member_uuid] = pos

    # Sort by order position
    ordered = sorted(members.items(), key=lambda x: x[1])

    if fmt == "tsv":
        for member_uuid, pos in ordered:
            title = _get_card_title(hord_root, member_uuid) or member_uuid
            card_type = _get_card_type(hord_root, member_uuid) or "?"
            expr_uuid = ""
            if expr_prefer:
                found = find_expression_for(hord_root, member_uuid, expr_prefer)
                if found:
                    expr_uuid = found
            click.echo(f"{pos}\t{card_type}\t{title}\t{member_uuid}\t{expr_uuid}")
        return

    # Human-readable output
    click.echo(f"{'═' * 60}")
    if holon_title:
        click.echo(f"  Holon: {holon_title}")
    click.echo(f"  {holon_uuid}")
    if expr_prefer:
        click.echo(f"  Expression: {expr_prefer}")
    click.echo(f"  Members: {len(members)}")
    click.echo(f"{'═' * 60}")
    click.echo()

    for member_uuid, pos in ordered:
        title = _get_card_title(hord_root, member_uuid) or member_uuid
        card_type = _get_card_type(hord_root, member_uuid) or "?"

        # Check for expression substitution
        expr_marker = ""
        if expr_prefer:
            expr_uuid = find_expression_for(hord_root, member_uuid, expr_prefer)
            if expr_uuid:
                expr_title = _get_card_title(hord_root, expr_uuid)
                expr_marker = f"  → expr: {expr_title or expr_uuid[:8]}"

        click.echo(f"  {pos:>3}. [{card_type}] {title}{expr_marker}")

    click.echo()


def _looks_like_uuid(s: str) -> bool:
    """Quick check if a string looks like a UUID."""
    return len(s) == 36 and s.count("-") == 4
