"""hord capture — quick-capture thoughts, notes, and observations into the hord."""

import os
import uuid as uuid_mod

import click

from hord.git_utils import find_hord_root, blob_hash, read_config
from hord.new import slugify, make_timestamp, TYPE_SUFFIX
from hord.quad import Quad, write_quads, quad_path, overlay_for_predicate, list_overlays


def capture_to_hord(hord_root: str, content: str,
                    tags: list[str] | None = None,
                    source: str = "",
                    title: str | None = None,
                    fmt: str | None = None) -> dict:
    """Create a capture card and compile it into quads in one step.

    Returns dict with uuid, path, tags, and quad count.
    This is the core function — used by both CLI and MCP.
    """
    if fmt is None:
        config = read_config(hord_root)
        fmt = config.get("format", "org")

    card_uuid = str(uuid_mod.uuid4())
    timestamp = make_timestamp()

    # Auto-generate title from first line of content if not given
    if title is None:
        first_line = content.split("\n")[0].strip()
        # Truncate long first lines
        if len(first_line) > 60:
            title = first_line[:57] + "..."
        else:
            title = first_line

    suffix = TYPE_SUFFIX["wh:cap"]
    slug = slugify(title)
    if not slug:
        slug = card_uuid[:8]

    ext = "org" if fmt == "org" else "md"
    filename = f"{slug}--{suffix}.{ext}"

    # Capture cards go to capture/ directory
    out_dir = os.path.join(hord_root, "capture")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    # Handle filename collision
    if os.path.exists(filepath):
        filename = f"{slug}_{card_uuid[:8]}--{suffix}.{ext}"
        filepath = os.path.join(out_dir, filename)

    # Generate file content
    if fmt == "org":
        file_content = _scaffold_capture_org(
            card_uuid, title, timestamp, content, tags, source)
    else:
        file_content = _scaffold_capture_md(
            card_uuid, title, timestamp, content, tags, source)

    with open(filepath, "w") as f:
        f.write(file_content)

    # Compile immediately — build quads and write to overlays
    try:
        context = blob_hash(filepath)
    except Exception:
        context = "unknown"

    quads = [
        Quad(card_uuid, "v:type", "wh:cap", context),
        Quad(card_uuid, "v:title", f"{title}\u2014{suffix}", context),
    ]

    if tags:
        for tag in tags:
            quads.append(Quad(card_uuid, "v:tag", tag, context))

    # Route to overlays or legacy
    use_overlays = bool(list_overlays(hord_root))
    if use_overlays:
        overlay_groups: dict[str, list[Quad]] = {}
        for q in quads:
            ov = overlay_for_predicate(q.predicate)
            overlay_groups.setdefault(ov, []).append(q)
        for ov, ov_quads in overlay_groups.items():
            qpath = quad_path(hord_root, card_uuid, overlay=ov)
            write_quads(qpath, ov_quads)
    else:
        qpath = quad_path(hord_root, card_uuid)
        write_quads(qpath, quads)

    # Update index
    relpath = os.path.relpath(filepath, hord_root)
    _append_index(hord_root, relpath, card_uuid)

    return {
        "uuid": card_uuid,
        "path": relpath,
        "tags": tags or [],
        "quads": len(quads),
    }


def _append_index(hord_root: str, path: str, uuid: str) -> None:
    """Append a single entry to index.tsv without rewriting the whole file."""
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    with open(index_path, "a") as f:
        f.write(f"{path}\t{uuid}\n")


def _scaffold_capture_org(uuid: str, title: str, timestamp: str,
                          content: str, tags: list[str] | None,
                          source: str) -> str:
    suffix = TYPE_SUFFIX["wh:cap"]
    display_title = f"{title}\u2014{suffix}"

    props = [
        "  :PROPERTIES:",
        f"  :ID:        {uuid}",
        "  :TYPE:      wh:cap",
        f"  :CREATED:   {timestamp}",
    ]
    if source:
        props.append(f"  :SOURCE:    {source}")
    if tags:
        props.append(f"  :TAGS:      {' '.join(tags)}")
    props.append("  :END:")

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
        content,
        "",
    ]
    return "\n".join(lines)


def _scaffold_capture_md(uuid: str, title: str, timestamp: str,
                         content: str, tags: list[str] | None,
                         source: str) -> str:
    suffix = TYPE_SUFFIX["wh:cap"]
    display_title = f"{title}\u2014{suffix}"

    lines = [
        "---",
        f"id: {uuid}",
        "type: wh:cap",
        f"title: {display_title}",
        f"created: {timestamp}",
    ]
    if source:
        lines.append(f"source: {source}")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines += [
        "---",
        "",
        f"# {display_title}",
        "",
        content,
        "",
    ]
    return "\n".join(lines)


@click.command("capture")
@click.argument("content", required=False)
@click.option("--tags", "-t", default="",
              help="Space-separated tags (e.g. 'hoard tps')")
@click.option("--source", "-s", default="",
              help="Source context (e.g. reading, conversation, observation)")
@click.option("--title", default=None,
              help="Title (default: first line of content)")
@click.option("--stdin", "from_stdin", is_flag=True,
              help="Read content from stdin")
def capture_cmd(content, tags, source, title, from_stdin):
    """Capture a thought, note, or observation into the hord.

    Creates a capture card (wh:cap) in capture/ and compiles
    it into quads immediately. Faster than 'hord new' — designed
    for quick capture with minimal friction.

    Content can be passed as an argument, or piped via --stdin.

    Examples:

        hord capture "Kanban is a pull system" -t "tps lean"

        hord capture "Interesting paper on X" -s reading -t research

        echo "Long note..." | hord capture --stdin -t notes
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord. Run 'hord init' first.", err=True)
        raise SystemExit(1)

    if from_stdin:
        import sys
        content = sys.stdin.read().strip()
    elif content is None:
        click.echo("Error: provide content as argument or use --stdin.", err=True)
        raise SystemExit(1)

    tag_list = [t.strip() for t in tags.split() if t.strip()] if tags else []

    result = capture_to_hord(
        hord_root, content,
        tags=tag_list,
        source=source,
        title=title,
    )

    click.echo(f"Captured → {result['path']}")
    click.echo(f"  UUID: {result['uuid']}")
    if result['tags']:
        click.echo(f"  Tags: {', '.join(result['tags'])}")
    click.echo(f"  Quads: {result['quads']}")
