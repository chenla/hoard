"""hord status — check for stale metadata."""

import os

import click

from hord.git_utils import find_hord_root, blob_hash
from hord.quad import read_quads, quad_path


@click.command("status")
@click.option("--verbose", "-v", is_flag=True, help="Show all entries, not just stale ones")
def status_cmd(verbose):
    """Show entities whose content has changed since last compile.

    Compares the git blob hash stored in each quad's context
    column against the current blob hash of the source file.
    Reports entities that need recompilation.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if not os.path.exists(index_path):
        click.echo("No index found. Run 'hord compile' first.", err=True)
        raise SystemExit(1)

    # Read index
    entries = []
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                entries.append((parts[0], parts[1]))

    if not entries:
        click.echo("Index is empty. Run 'hord compile' first.")
        return

    stale = []
    fresh = []
    missing = []

    for path, uuid in entries:
        filepath = os.path.join(hord_root, path)

        if not os.path.exists(filepath):
            missing.append((path, uuid))
            continue

        # Get current blob hash
        try:
            current_hash = blob_hash(filepath)
        except Exception:
            missing.append((path, uuid))
            continue

        # Get stored context hash from quads
        qpath = quad_path(hord_root, uuid)
        quads = read_quads(qpath)

        if not quads:
            stale.append((path, uuid, "no quads"))
            continue

        # Use first quad's context as the stored hash
        stored_hash = quads[0].context

        if stored_hash == current_hash:
            fresh.append((path, uuid))
        else:
            stale.append((path, uuid, "content changed"))

    # Report
    if stale:
        click.echo(f"Stale ({len(stale)}):")
        for path, uuid, reason in stale:
            click.echo(f"  ✗ {path}  ({reason})")
        click.echo()

    if missing:
        click.echo(f"Missing ({len(missing)}):")
        for path, uuid in missing:
            click.echo(f"  ? {path}")
        click.echo()

    if verbose and fresh:
        click.echo(f"Fresh ({len(fresh)}):")
        for path, uuid in fresh:
            click.echo(f"  ✓ {path}")
        click.echo()

    if not stale and not missing:
        click.echo(f"All {len(fresh)} entities are fresh.")
    else:
        total_issues = len(stale) + len(missing)
        click.echo(f"{total_issues} issue(s). Run 'hord compile' to update.")
