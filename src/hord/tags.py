"""hord tags — list and audit tag usage across the hord."""

import os

import click

from hord.git_utils import find_hord_root
from hord.quad import read_quads, read_all_quads, find_all_quads_dirs


def collect_tags(hord_root: str) -> dict[str, list[str]]:
    """Scan all quads and collect tag → [list of entity UUIDs].
    Returns a dict mapping tag labels to the UUIDs that carry them."""
    tags: dict[str, list[str]] = {}

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
                    if q.predicate == "v:tag":
                        tags.setdefault(q.object, []).append(q.subject)

    return tags


def find_tag_cards(hord_root: str) -> set[str]:
    """Find tag labels that have a corresponding wh:tag card.
    Matches by title (lowercase) against tag labels."""
    defined = set()

    for quads_dir in find_all_quads_dirs(hord_root):
        for prefix_dir in os.listdir(quads_dir):
            prefix_path = os.path.join(quads_dir, prefix_dir)
            if not os.path.isdir(prefix_path):
                continue
            for fname in os.listdir(prefix_path):
                if not fname.endswith(".tsv"):
                    continue
                fpath = os.path.join(prefix_path, fname)
                quads = read_quads(fpath)
                is_tag = False
                title = None
                for q in quads:
                    if q.predicate == "v:type" and q.object == "wh:tag":
                        is_tag = True
                    if q.predicate == "v:title":
                        title = q.object
                if is_tag and title:
                    # Strip the —15 suffix for matching
                    clean = title.rsplit("\u2014", 1)[0].strip().lower()
                    defined.add(clean)

    return defined


@click.command("tags")
@click.option("--undefined", "-u", is_flag=True,
              help="Show only tags without a tag card")
def tags_cmd(undefined):
    """List tags and their usage across the hord.

    Shows each tag, how many cards use it, and whether it
    has a corresponding tag card (wh:tag definition).

    Use --undefined to see only tags that lack definitions.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    tags = collect_tags(hord_root)
    if not tags:
        click.echo("No tags found. Add :TAGS: to card property drawers.")
        return

    defined = find_tag_cards(hord_root)

    # Sort by count (descending), then alphabetical
    sorted_tags = sorted(tags.items(), key=lambda x: (-len(x[1]), x[0]))

    if undefined:
        sorted_tags = [(t, uuids) for t, uuids in sorted_tags
                       if t.lower() not in defined]
        if not sorted_tags:
            click.echo("All tags have definitions.")
            return

    # Display
    click.echo(f"{'Tag':<24} {'Count':>5}  {'Defined':>7}")
    click.echo(f"{'─' * 24} {'─' * 5}  {'─' * 7}")

    defined_count = 0
    undefined_count = 0
    for tag, uuids in sorted_tags:
        is_defined = tag.lower() in defined
        marker = "  yes" if is_defined else "   --"
        click.echo(f"{tag:<24} {len(uuids):>5}  {marker}")
        if is_defined:
            defined_count += 1
        else:
            undefined_count += 1

    click.echo()
    click.echo(f"{len(tags)} tags, {defined_count} defined, {undefined_count} undefined")
