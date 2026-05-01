"""hord add — add files (blobs) to the hord and link them to cards.

Copies a file into lib/blob/ using the citekey naming convention
(author:yearslug.ext), optionally creates or links a wh:wrk card,
and can generate a LOD context file alongside the blob.

Citekey format: author:yearslug  (e.g. scott:1998seeing)
Blob path:     lib/blob/author:yearslug.ext
Context file:  lib/blob/author:yearslug--context.md
"""

import os
import re
import shutil
import uuid
from datetime import datetime, timezone

import click

from hord.git_utils import find_hord_root, read_config
from hord.new import TYPE_SUFFIX, slugify


def _make_timestamp() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%dT%H:%M")


def _normalise_citekey(key: str) -> str:
    """Normalise a citekey: lowercase, strip whitespace."""
    return key.strip().lower()


def _guess_citekey_from_filename(filename: str) -> str:
    """Try to extract a citekey from an existing filename.

    Handles patterns like:
      scott:1998seeing.pdf      → scott:1998seeing
      scott 1998seeing.pdf      → scott:1998seeing
      Scott_1998_Seeing.pdf     → scott:1998seeing
    """
    name = os.path.splitext(filename)[0]

    # Already has colon separator
    if re.match(r"^[a-z_]+:\d{4}", name):
        return name.lower()

    # Space separator (common in older collections)
    m = re.match(r"^([a-z_]+)\s+(\d{4})(.*)$", name, re.IGNORECASE)
    if m:
        author = m.group(1).lower().replace("_", "")
        year = m.group(2)
        slug = m.group(3).lower().replace(" ", "").replace("_", "").replace("-", "")
        return f"{author}:{year}{slug}"

    # Underscore separator
    m = re.match(r"^([a-z]+)_(\d{4})_?(.*)$", name, re.IGNORECASE)
    if m:
        author = m.group(1).lower()
        year = m.group(2)
        slug = m.group(3).lower().replace(" ", "").replace("_", "").replace("-", "")
        return f"{author}:{year}{slug}"

    return ""


def _find_card_by_citekey(hord_root: str, citekey: str) -> str:
    """Search for an existing card with a matching :CITEKEY: property.

    Returns the UUID if found, empty string otherwise.
    """
    for subdir in ("content", "capture"):
        content_dir = os.path.join(hord_root, subdir)
        if not os.path.isdir(content_dir):
            continue
        for fname in os.listdir(content_dir):
            if not fname.endswith(".org"):
                continue
            fpath = os.path.join(content_dir, fname)
            try:
                with open(fpath) as f:
                    head = f.read(2048)
            except (OSError, UnicodeDecodeError):
                continue

            # Check :CITEKEY: property
            m = re.search(r":CITEKEY:\s+(\S+)", head)
            if m and _normalise_citekey(m.group(1).rstrip(",")) == citekey:
                # Extract UUID
                uid_m = re.search(r":ID:\s+(\S+)", head)
                if uid_m:
                    return uid_m.group(1)

            # Check legacy #+ROAM_KEY: cite:key
            m = re.search(r"#\+ROAM_KEY:\s+cite:(\S+)", head)
            if m and _normalise_citekey(m.group(1)) == citekey:
                uid_m = re.search(r":ID:\s+(\S+)", head)
                if uid_m:
                    return uid_m.group(1)

            # Check :CUSTOM_ID: (legacy biblio entries)
            m = re.search(r":CUSTOM_ID:\s+(\S+)", head)
            if m and _normalise_citekey(m.group(1)) == citekey:
                uid_m = re.search(r":ID:\s+(\S+)", head)
                if uid_m:
                    return uid_m.group(1)

    return ""


def _create_work_card(hord_root: str, citekey: str, title: str,
                      author: str, year: str, fmt: str,
                      blob_relpath: str) -> str:
    """Create a new wh:wrk card for the blob. Returns the UUID."""
    card_uuid = str(uuid.uuid4())
    timestamp = _make_timestamp()
    suffix = TYPE_SUFFIX["wh:wrk"]
    display_title = f"{title}\u2014{suffix}"
    slug = slugify(title)

    if fmt == "org":
        content = _scaffold_work_org(
            card_uuid, display_title, timestamp, citekey,
            author, year, blob_relpath)
        filename = f"{slug}--{suffix}.org"
    else:
        content = _scaffold_work_md(
            card_uuid, display_title, timestamp, citekey,
            author, year, blob_relpath)
        filename = f"{slug}--{suffix}.md"

    out_dir = os.path.join(hord_root, "content")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    # Don't overwrite
    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        counter = 2
        while os.path.exists(filepath):
            filepath = os.path.join(out_dir, f"{base}_{counter}{ext}")
            counter += 1

    with open(filepath, "w") as f:
        f.write(content)

    return card_uuid


def _scaffold_work_org(card_uuid: str, display_title: str,
                       timestamp: str, citekey: str,
                       author: str, year: str,
                       blob_relpath: str) -> str:
    """Generate an org-mode wh:wrk card for a blob."""
    lines = [
        "#   -*- mode: org; fill-column: 60 -*-",
        "#+STARTUP: showall",
        f"#+TITLE:   {display_title}",
        '#+FILETAGS: "hord" "work"',
        "",
        f"* {display_title}",
        "  :PROPERTIES:",
        f"  :ID:        {card_uuid}",
        "  :TYPE:      wh:wrk",
        f"  :CREATED:   {timestamp}",
        f"  :CITEKEY:   {citekey}",
    ]
    if author:
        lines.append(f"  :AUTHOR:    {author}")
    lines += [
        "  :LICENCE:   MIT/CC BY-SA 4.0",
        "  :END:",
        "",
        "** Relations",
        f"   - PT :: {display_title}",
        "",
        "** Bibliographic Data",
    ]
    if author:
        lines.append(f"   - Author :: {author}")
    if year:
        lines.append(f"   - Year :: {year}")
    lines += [
        "",
        "** Notes",
        f"   :PROPERTIES:",
        f"   :NOTER_DOCUMENT: {blob_relpath}",
        f"   :END:",
        "",
        "",
        "** References",
        "",
    ]
    return "\n".join(lines)


def _scaffold_work_md(card_uuid: str, display_title: str,
                      timestamp: str, citekey: str,
                      author: str, year: str,
                      blob_relpath: str) -> str:
    """Generate a markdown wh:wrk card for a blob."""
    lines = [
        "---",
        f"id: {card_uuid}",
        "type: wh:wrk",
        f"title: {display_title}",
        f"created: {timestamp}",
        f"citekey: {citekey}",
    ]
    if author:
        lines.append(f"author: {author}")
    if year:
        lines.append(f"year: {year}")
    lines += [
        "license: MIT/CC BY-SA 4.0",
        "relations:",
        f"  - \"PT: {display_title}\"",
        "---",
        "",
        f"# {display_title}",
        "",
        f"Blob: `{blob_relpath}`",
        "",
    ]
    return "\n".join(lines)


def _generate_context_stub(citekey: str, title: str,
                           author: str, year: str,
                           ext: str) -> str:
    """Generate a LOD context file stub for a blob.

    The context file is a markdown summary that sits alongside
    the blob, giving AI a token-efficient way to understand
    what the file contains without reading the whole thing.
    """
    lines = [
        f"# {title}",
        "",
    ]
    if author or year:
        meta_parts = []
        if author:
            meta_parts.append(f"**Author:** {author}")
        if year:
            meta_parts.append(f"**Year:** {year}")
        lines.append(" | ".join(meta_parts))
        lines.append("")

    lines += [
        f"**Citekey:** `{citekey}`",
        f"**Format:** {ext.upper().lstrip('.')}",
        "",
        "## Summary",
        "",
        "<!-- Write a 2-3 sentence summary of this work. -->",
        "",
        "## Key Ideas",
        "",
        "<!-- Bullet points of the main arguments or contributions. -->",
        "",
        "## Relevance",
        "",
        "<!-- How does this connect to your hord? Which cards does it inform? -->",
        "",
    ]
    return "\n".join(lines)


def _parse_citekey_parts(citekey: str) -> tuple:
    """Extract author, year, and slug from a citekey.

    Returns (author, year, slug).
    """
    m = re.match(r"^([^:]+):(\d{4})(.*)", citekey)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return "", "", ""


@click.command("add")
@click.argument("filepath")
@click.option("--key", "-k", "citekey", default=None,
              help="Citekey (author:yearslug). Auto-derived from filename if omitted.")
@click.option("--title", "-t", default=None,
              help="Title of the work. Derived from citekey if omitted.")
@click.option("--author", "-a", default=None,
              help="Author name(s).")
@click.option("--year", "-y", default=None,
              help="Publication year.")
@click.option("--card/--no-card", "create_card", default=True,
              help="Create a wh:wrk card for this blob (default: yes).")
@click.option("--context/--no-context", "create_context", default=False,
              help="Generate a LOD context file stub alongside the blob.")
@click.option("--link", "-l", "link_uuid", default=None,
              help="UUID of an existing card to link (sets :NOTER_DOCUMENT:).")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["org", "md"]),
              default=None,
              help="Card format (default: from config.toml)")
@click.option("--move/--copy", "move_file", default=False,
              help="Move instead of copy (default: copy).")
@click.option("--dry-run", is_flag=True,
              help="Show what would happen without writing files.")
@click.option("--verbose", "-v", is_flag=True)
def add_cmd(filepath, citekey, title, author, year, create_card,
            create_context, link_uuid, fmt, move_file, dry_run, verbose):
    """Add a file (PDF, EPUB, image, etc.) to the hord blob store.

    Copies the file into lib/blob/ with a citekey-based filename,
    and optionally creates a wh:wrk card linked to it.

    The citekey is derived from the filename if not provided
    explicitly. The format is author:yearslug (e.g. scott:1998seeing).

    Examples:

        hord add paper.pdf -k scott:1998seeing

        hord add ~/Downloads/report.pdf -k jones:2026wiki -t "The Wiki Problem"

        hord add photo.jpg --no-card

        hord add book.epub -k braudel:1992civilization --context

        hord add paper.pdf --link 550e8400-e29b-41d4-a716-446655440000
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord. Run 'hord init' first.",
                    err=True)
        raise SystemExit(1)

    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        click.echo(f"Error: file not found: {filepath}", err=True)
        raise SystemExit(1)

    # Default format from config
    if fmt is None:
        config = read_config(hord_root)
        fmt = config.get("format", "org")

    basename = os.path.basename(filepath)
    ext = os.path.splitext(basename)[1]

    # ── Resolve citekey ──────────────────────────────────
    if not citekey:
        citekey = _guess_citekey_from_filename(basename)

    if not citekey:
        click.echo("Error: could not derive citekey from filename.", err=True)
        click.echo("Provide one with --key / -k (format: author:yearslug)",
                    err=True)
        raise SystemExit(1)

    citekey = _normalise_citekey(citekey)

    # Parse citekey parts
    ck_author, ck_year, ck_slug = _parse_citekey_parts(citekey)

    # Use explicit overrides or fall back to citekey parts
    if not author and ck_author:
        author = ck_author.title()
    if not year and ck_year:
        year = ck_year
    if not title:
        if ck_slug:
            # Turn slug into a rough title: "seeing" → "Seeing"
            title = ck_slug.replace("-", " ").replace("_", " ").strip().title()
            if author and year:
                title = f"{title} ({author}, {year})"
        elif author and year:
            title = f"{author} {year}"
        else:
            title = citekey

    # ── Determine blob destination ───────────────────────
    blob_dir = os.path.join(hord_root, "lib", "blob")
    blob_filename = f"{citekey}{ext}"
    blob_path = os.path.join(blob_dir, blob_filename)
    blob_relpath = os.path.join("lib", "blob", blob_filename)

    # ── Context file ─────────────────────────────────────
    context_filename = f"{citekey}--context.md"
    context_path = os.path.join(blob_dir, context_filename)

    # ── Report plan ──────────────────────────────────────
    click.echo(f"Citekey: {citekey}")
    click.echo(f"  File: {basename} → lib/blob/{blob_filename}")

    if os.path.exists(blob_path):
        click.echo(f"  Warning: blob already exists at {blob_relpath}")
        if not dry_run:
            click.echo("  Use a different citekey or remove the existing file.")
            raise SystemExit(1)

    # Check for existing linked card
    existing_uuid = ""
    if link_uuid:
        existing_uuid = link_uuid
        click.echo(f"  Linking to existing card: {link_uuid}")
    else:
        existing_uuid = _find_card_by_citekey(hord_root, citekey)
        if existing_uuid:
            click.echo(f"  Found existing card: {existing_uuid}")
            create_card = False

    if create_card and not existing_uuid:
        click.echo(f"  Will create wh:wrk card: {title}")

    if create_context:
        click.echo(f"  Will create context file: {context_filename}")

    if dry_run:
        click.echo("\nDry run — no files written.")
        return

    # ── Execute ──────────────────────────────────────────

    # 1. Copy/move blob
    os.makedirs(blob_dir, exist_ok=True)
    if move_file:
        shutil.move(filepath, blob_path)
        if verbose:
            click.echo(f"  Moved → {blob_relpath}")
    else:
        shutil.copy2(filepath, blob_path)
        if verbose:
            click.echo(f"  Copied → {blob_relpath}")

    # 2. Create card if needed
    card_uuid = existing_uuid
    if create_card and not existing_uuid:
        card_uuid = _create_work_card(
            hord_root, citekey, title, author, year, fmt, blob_relpath)
        click.echo(f"  Created card: {card_uuid}")

    # 3. Generate context stub
    if create_context and not os.path.exists(context_path):
        stub = _generate_context_stub(citekey, title, author, year, ext)
        with open(context_path, "w") as f:
            f.write(stub)
        if verbose:
            click.echo(f"  Created context file: {context_filename}")

    # 4. Update existing card with :NOTER_DOCUMENT: if linking
    if link_uuid:
        _update_card_noter(hord_root, link_uuid, blob_relpath, verbose)

    click.echo("")
    click.echo(f"Added {blob_filename} to lib/blob/")
    if card_uuid:
        click.echo(f"  Card UUID: {card_uuid}")
        click.echo(f"  cite:{citekey}")


def _update_card_noter(hord_root: str, card_uuid: str,
                       blob_relpath: str, verbose: bool) -> None:
    """Add :NOTER_DOCUMENT: to an existing card's property drawer."""
    for subdir in ("content", "capture"):
        content_dir = os.path.join(hord_root, subdir)
        if not os.path.isdir(content_dir):
            continue
        for fname in os.listdir(content_dir):
            if not fname.endswith(".org"):
                continue
            fpath = os.path.join(content_dir, fname)
            try:
                with open(fpath) as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            if f":ID:        {card_uuid}" not in content:
                # Also try with varying whitespace
                if f":ID:" not in content or card_uuid not in content:
                    continue

            # Check if NOTER_DOCUMENT already set
            if ":NOTER_DOCUMENT:" in content:
                if verbose:
                    click.echo(f"  Card already has :NOTER_DOCUMENT:")
                return

            # Insert before :END:
            # Find the first :END: after the card's :ID:
            id_pos = content.find(card_uuid)
            if id_pos == -1:
                continue
            end_pos = content.find(":END:", id_pos)
            if end_pos == -1:
                continue

            noter_line = f"  :NOTER_DOCUMENT: {blob_relpath}\n"
            new_content = content[:end_pos] + noter_line + content[end_pos:]

            with open(fpath, "w") as f:
                f.write(new_content)

            if verbose:
                click.echo(f"  Updated {fname} with :NOTER_DOCUMENT:")
            return
