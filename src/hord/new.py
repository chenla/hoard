"""hord new — create a new card with UUID and metadata scaffold."""

import os
import re
import uuid
from datetime import datetime, timezone

import click

from hord.git_utils import find_hord_root, read_config


# Entity type shortcuts — accept short names or full vocab IDs
TYPE_SHORTCUTS = {
    "con": "wh:con",
    "concept": "wh:con",
    "pat": "wh:pat",
    "pattern": "wh:pat",
    "key": "wh:key",
    "keystone": "wh:key",
    "wrk": "wh:wrk",
    "work": "wh:wrk",
    "per": "wh:per",
    "person": "wh:per",
    "cat": "wh:cat",
    "category": "wh:cat",
    "sys": "wh:sys",
    "system": "wh:sys",
    "pla": "wh:pla",
    "place": "wh:pla",
    "evt": "wh:evt",
    "event": "wh:evt",
    "obj": "wh:obj",
    "object": "wh:obj",
    "org": "wh:org",
    "organization": "wh:org",
    "cap": "wh:cap",
    "capture": "wh:cap",
    "tag": "wh:tag",
}

# Map vocab IDs to filename suffixes
TYPE_SUFFIX = {
    "wh:pat": "3",
    "wh:con": "4",
    "wh:key": "5",
    "wh:wrk": "6",
    "wh:per": "7",
    "wh:cat": "8",
    "wh:sys": "9",
    "wh:pla": "10",
    "wh:evt": "11",
    "wh:obj": "12",
    "wh:org": "13",
    "wh:cap": "14",
    "wh:tag": "15",
}


def slugify(title: str) -> str:
    """Convert a title to a filename-safe slug.

    Replaces spaces with underscores, strips non-alphanumeric
    characters except hyphens and underscores.
    """
    slug = title.replace(" ", "_")
    slug = re.sub(r"[^\w\-]", "", slug, flags=re.ASCII)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")


def make_timestamp() -> str:
    """Create a timestamp in the Hoard format."""
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%dT%H:%M")


def scaffold_org(card_uuid: str, title: str, entity_type: str,
                 timestamp: str, source: str = "") -> str:
    """Generate org-mode card content."""
    suffix = TYPE_SUFFIX.get(entity_type, "4")
    display_title = f"{title}\u2014{suffix}"

    props = [
        "  :PROPERTIES:",
        f"  :ID:        {card_uuid}",
        f"  :TYPE:      {entity_type}",
        f"  :CREATED:   {timestamp}",
    ]
    if source:
        props.append(f"  :SOURCE:    {source}")
    props.append("  :END:")

    if entity_type == "wh:tag":
        lines = [
            "#   -*- mode: org; fill-column: 60 -*-",
            "#+STARTUP: showall",
            f"#+TITLE:   {display_title}",
            "",
            f"* {display_title}",
            *props,
            "",
            "** Notes",
            "",
            "",
            "** Processing",
            "",
            "",
        ]
    else:
        lines = [
            "#   -*- mode: org; fill-column: 60 -*-",
            "#+STARTUP: showall",
            f"#+TITLE:   {display_title}",
            "",
            f"* {display_title}",
            *props,
            "",
            "** Relations",
            f"   - PT :: {display_title}",
            "",
            "** Notes",
            "",
            "",
        ]
    return "\n".join(lines)


def scaffold_md(card_uuid: str, title: str, entity_type: str,
                timestamp: str, source: str = "") -> str:
    """Generate markdown card content."""
    suffix = TYPE_SUFFIX.get(entity_type, "4")
    display_title = f"{title}\u2014{suffix}"

    lines = [
        "---",
        f"id: {card_uuid}",
        f"type: {entity_type}",
        f"title: {display_title}",
        f"created: {timestamp}",
    ]
    if source:
        lines.append(f"source: {source}")
    lines += [
        "relations:",
        f"  - \"PT: {display_title}\"",
        "aliases: []",
        "---",
        "",
        f"# {display_title}",
        "",
        "",
    ]
    return "\n".join(lines)


@click.command("new")
@click.argument("title")
@click.option("--type", "-t", "entity_type", default="con",
              help="Entity type: con, pat, key, wrk, per, cat, sys, pla, evt, obj, org (or wh:con etc.)")
@click.option("--format", "-f", "fmt", type=click.Choice(["org", "md"]),
              default=None, help="File format (default: from config.toml)")
@click.option("--dir", "-d", "content_dir", default="content",
              help="Content directory (default: content/)")
@click.option("--source", "-s", default="",
              help="Source context (e.g. reading, conversation, observation)")
@click.option("--edit", "-e", is_flag=True,
              help="Open the new file in $EDITOR")
def new_cmd(title, entity_type, fmt, content_dir, source, edit):
    """Create a new card with a UUID and metadata scaffold.

    TITLE is the card's display name (e.g. "Kanban" or
    "Taiichi Ohno"). The filename and type suffix are
    generated automatically.

    Examples:

        hord new "Kanban" -t con

        hord new "Taiichi Ohno" -t per

        hord new "My Book" -t wrk -f md
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord. Run 'hord init' first.", err=True)
        raise SystemExit(1)

    # Default format from config if not specified on command line
    if fmt is None:
        config = read_config(hord_root)
        fmt = config.get("format", "org")

    # Resolve entity type
    etype = entity_type.lower()
    if etype.startswith("wh:"):
        resolved_type = etype
    else:
        resolved_type = TYPE_SHORTCUTS.get(etype)
        if not resolved_type:
            click.echo(f"Error: unknown type '{entity_type}'", err=True)
            click.echo("Valid types: " + ", ".join(sorted(TYPE_SHORTCUTS.keys())), err=True)
            raise SystemExit(1)

    # Generate UUID and timestamp
    card_uuid = str(uuid.uuid4())
    timestamp = make_timestamp()

    # Default capture cards to capture/ directory
    if resolved_type == "wh:cap" and content_dir == "content":
        content_dir = "capture"

    # Build filename
    suffix = TYPE_SUFFIX.get(resolved_type, "4")
    slug = slugify(title)
    ext = "org" if fmt == "org" else "md"
    filename = f"{slug}--{suffix}.{ext}"

    # Ensure content directory exists
    out_dir = os.path.join(hord_root, content_dir)
    os.makedirs(out_dir, exist_ok=True)

    filepath = os.path.join(out_dir, filename)

    # Don't overwrite existing files
    if os.path.exists(filepath):
        click.echo(f"Error: file already exists: {filepath}", err=True)
        raise SystemExit(1)

    # Generate content
    if fmt == "org":
        content = scaffold_org(card_uuid, title, resolved_type, timestamp, source)
    else:
        content = scaffold_md(card_uuid, title, resolved_type, timestamp, source)

    with open(filepath, "w") as f:
        f.write(content)

    relpath = os.path.relpath(filepath, hord_root)
    click.echo(f"Created {relpath}")
    click.echo(f"  UUID: {card_uuid}")
    click.echo(f"  Type: {resolved_type}")

    # Open in editor if requested
    if edit:
        editor = os.environ.get("EDITOR", "vi")
        os.execlp(editor, editor, filepath)
