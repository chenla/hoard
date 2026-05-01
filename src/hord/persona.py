"""hord persona — manage persona overlays and annotate cards by role."""

import os

import click

from hord.git_utils import find_hord_root
from hord.quad import (Quad, write_quads, read_quads, quad_path,
                       read_all_quads, list_overlays, find_all_quads_dirs)
from hord.vocab import Vocabulary, find_vocab
from hord.query import load_index, resolve_uuid_label


def persona_overlays(hord_root: str) -> list[str]:
    """Return list of persona overlay names (without the 'persona-' prefix)."""
    return [
        ov.removeprefix("persona-")
        for ov in list_overlays(hord_root)
        if ov.startswith("persona-")
    ]


def ensure_persona(hord_root: str, name: str) -> str:
    """Create persona overlay directory if it doesn't exist.
    Returns the overlay name (persona-<name>)."""
    overlay_name = f"persona-{name}"
    quads_dir = os.path.join(hord_root, ".hord", "overlays",
                             overlay_name, "quads")
    os.makedirs(quads_dir, exist_ok=True)
    return overlay_name


@click.group("persona")
def persona_cmd():
    """Manage persona overlays — roles, views, and annotations.

    Personas are views on the same data through different roles.
    Each persona gets its own overlay directory for role-specific
    annotations (relevance, notes, priority).

    Examples:

        hord persona create researcher

        hord persona annotate researcher Kanban--4 --relevant --note "Core to TPS study"

        hord persona list

        hord persona show researcher
    """
    pass


@persona_cmd.command("create")
@click.argument("name")
def persona_create(name):
    """Create a new persona overlay.

    NAME is the persona identifier (e.g. researcher, musician, work).
    Creates the overlay directory and optionally a persona card.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    name = name.lower().replace(" ", "-")
    overlay_name = ensure_persona(hord_root, name)
    click.echo(f"Created persona overlay: {overlay_name}")
    click.echo(f"  Directory: .hord/overlays/{overlay_name}/quads/")
    click.echo()
    click.echo(f"  To create a persona card: hord new \"{name}\" --type persona")


@persona_cmd.command("list")
def persona_list():
    """List all persona overlays and their quad counts."""
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    personas = persona_overlays(hord_root)
    if not personas:
        click.echo("No personas. Create one with: hord persona create <name>")
        return

    click.echo(f"{'Persona':<24} {'Cards':>6}")
    click.echo(f"{'─' * 24} {'─' * 6}")

    for name in sorted(personas):
        overlay = f"persona-{name}"
        quads_dir = os.path.join(hord_root, ".hord", "overlays",
                                 overlay, "quads")
        # Count unique subjects (cards with annotations)
        subjects = set()
        if os.path.isdir(quads_dir):
            for prefix_dir in os.listdir(quads_dir):
                prefix_path = os.path.join(quads_dir, prefix_dir)
                if not os.path.isdir(prefix_path):
                    continue
                for fname in os.listdir(prefix_path):
                    if fname.endswith(".tsv"):
                        subjects.add(fname.removesuffix(".tsv"))
        click.echo(f"{name:<24} {len(subjects):>6}")

    click.echo()
    click.echo(f"{len(personas)} personas")


@persona_cmd.command("annotate")
@click.argument("persona_name")
@click.argument("term")
@click.option("--relevant", "-r", is_flag=True,
              help="Mark card as relevant to this persona")
@click.option("--note", "-n", default="",
              help="Add a role-specific note")
@click.option("--priority", "-p", type=click.Choice(["high", "medium", "low"]),
              default=None, help="Set priority for this role")
def persona_annotate(persona_name, term, relevant, note, priority):
    """Annotate a card from a specific persona's perspective.

    PERSONA_NAME is the persona (e.g. researcher).
    TERM is the card to annotate (UUID, filename, or path).
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    # Resolve card
    index = load_index(hord_root)
    uuid = index.get(term)
    if uuid is None:
        for key, val in index.items():
            if key.startswith(term) and len(term) >= 4:
                uuid = val
                break
    if uuid is None:
        click.echo(f"Not found: {term}", err=True)
        raise SystemExit(1)

    # Ensure persona overlay exists
    persona_name = persona_name.lower().replace(" ", "-")
    overlay_name = ensure_persona(hord_root, persona_name)

    # Build quads
    quads = []
    context = "persona"  # persona annotations aren't tied to a source file

    if relevant:
        quads.append(Quad(uuid, "v:p-relevant", "true", context))
    if note:
        quads.append(Quad(uuid, "v:p-note", note, context))
    if priority:
        quads.append(Quad(uuid, "v:p-priority", priority, context))

    if not quads:
        click.echo("Nothing to annotate. Use --relevant, --note, or --priority.")
        return

    # Read existing quads for this entity in this persona overlay
    qpath = quad_path(hord_root, uuid, overlay=overlay_name)
    existing = read_quads(qpath)

    # Merge: replace existing predicates, append new ones
    existing_preds = {}
    for q in existing:
        existing_preds[q.predicate] = q

    for q in quads:
        existing_preds[q.predicate] = q

    write_quads(qpath, list(existing_preds.values()))

    # Get title for display
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None
    title = resolve_uuid_label(hord_root, uuid, vocab)

    click.echo(f"Annotated {title} as {persona_name}:")
    for q in quads:
        click.echo(f"  {q.predicate}: {q.object}")


@persona_cmd.command("show")
@click.argument("persona_name")
def persona_show(persona_name):
    """Show all cards annotated by a persona."""
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    persona_name = persona_name.lower().replace(" ", "-")
    overlay_name = f"persona-{persona_name}"
    quads_dir = os.path.join(hord_root, ".hord", "overlays",
                             overlay_name, "quads")

    if not os.path.isdir(quads_dir):
        click.echo(f"Persona '{persona_name}' not found.", err=True)
        raise SystemExit(1)

    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    entries = []
    for prefix_dir in os.listdir(quads_dir):
        prefix_path = os.path.join(quads_dir, prefix_dir)
        if not os.path.isdir(prefix_path):
            continue
        for fname in os.listdir(prefix_path):
            if not fname.endswith(".tsv"):
                continue
            uuid = fname.removesuffix(".tsv")
            fpath = os.path.join(prefix_path, fname)
            pquads = read_quads(fpath)

            title = resolve_uuid_label(hord_root, uuid, vocab)
            relevant = False
            priority = ""
            note = ""
            for q in pquads:
                if q.predicate == "v:p-relevant":
                    relevant = True
                elif q.predicate == "v:p-priority":
                    priority = q.object
                elif q.predicate == "v:p-note":
                    note = q.object

            entries.append({
                "title": title,
                "relevant": relevant,
                "priority": priority,
                "note": note,
            })

    if not entries:
        click.echo(f"No annotations for persona '{persona_name}'.")
        return

    entries.sort(key=lambda e: (
        {"high": 0, "medium": 1, "low": 2, "": 3}.get(e["priority"], 3),
        e["title"].lower(),
    ))

    click.echo(f"Persona: {persona_name} ({len(entries)} cards)")
    click.echo()

    for e in entries:
        markers = []
        if e["relevant"]:
            markers.append("relevant")
        if e["priority"]:
            markers.append(e["priority"])
        marker_str = f"  [{', '.join(markers)}]" if markers else ""
        click.echo(f"  {e['title']}{marker_str}")
        if e["note"]:
            click.echo(f"    {e['note']}")
