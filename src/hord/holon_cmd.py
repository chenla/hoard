"""hord holon — list and inspect holons."""

import os

import click

from hord.git_utils import find_hord_root
from hord.quad import read_all_quads, quad_path, read_quads
from hord.vocab import Vocabulary, find_vocab
from hord.query import load_index, resolve_uuid_label
from hord.holon import find_expression_for, _get_card_type, _get_card_title


@click.group("holon")
def holon_cmd():
    """Inspect and query holons."""
    pass


@holon_cmd.command("list")
def holon_list():
    """List all holons in the hord."""
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if not os.path.exists(index_path):
        click.echo("No index found. Run 'hord compile' first.", err=True)
        raise SystemExit(1)

    holons = []
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                path, uuid = parts[0], parts[1]
                card_type = _get_card_type(hord_root, uuid)
                if card_type == "wh:holon":
                    title = _get_card_title(hord_root, uuid) or path
                    # Count members
                    member_count = 0
                    expr_prefer = None
                    for q in read_all_quads(hord_root, uuid):
                        if q.predicate == "v:h-member":
                            member_count += 1
                        elif q.predicate == "v:h-expr":
                            expr_prefer = q.object
                    holons.append((title, uuid, member_count, expr_prefer))

    if not holons:
        click.echo("No holons found.")
        return

    click.echo(f"{'Title':<40} {'Members':>7}  {'Expression':<20}  UUID")
    click.echo(f"{'─' * 40} {'─' * 7}  {'─' * 20}  {'─' * 36}")
    for title, uuid, count, expr in holons:
        expr_str = expr or "—"
        click.echo(f"{title:<40} {count:>7}  {expr_str:<20}  {uuid[:12]}…")


@holon_cmd.command("show")
@click.argument("term")
def holon_show(term):
    """Show a holon's members with expression substitution.

    TERM can be a holon name, slug, or UUID.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    index = load_index(hord_root)
    holon_uuid = index.get(term)
    if holon_uuid is None:
        for key, val in index.items():
            if key.startswith(term) and len(term) >= 4:
                holon_uuid = val
                break
    if holon_uuid is None:
        click.echo(f"Not found: {term}", err=True)
        raise SystemExit(1)

    holon_type = _get_card_type(hord_root, holon_uuid)
    if holon_type != "wh:holon":
        click.echo(f"'{term}' is not a holon (type: {holon_type})", err=True)
        raise SystemExit(1)

    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    holon_quads = read_all_quads(hord_root, holon_uuid)

    members = {}
    expr_prefer = None
    holon_title = None
    order_map = {}  # member_uuid → position

    for q in holon_quads:
        if q.predicate == "v:h-member":
            members[q.object] = 999
        elif q.predicate == "v:h-expr":
            expr_prefer = q.object
        elif q.predicate == "v:title":
            holon_title = q.object
        elif q.predicate == "v:h-order":
            # subject=member UUID, object=position, context=holon UUID
            try:
                order_map[q.subject] = int(q.object)
            except ValueError:
                pass

    # Apply ordering
    for member_uuid, pos in order_map.items():
        if member_uuid in members:
            members[member_uuid] = pos

    ordered = sorted(members.items(), key=lambda x: x[1])

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

        expr_marker = ""
        if expr_prefer:
            expr_uuid = find_expression_for(hord_root, member_uuid, expr_prefer)
            if expr_uuid:
                expr_title = _get_card_title(hord_root, expr_uuid)
                expr_marker = f"  → expr: {expr_title or expr_uuid[:8]}"

        click.echo(f"  {pos:>3}. [{card_type}] {title}{expr_marker}")

    click.echo()
