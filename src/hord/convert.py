"""hord convert — translate between org-mode and markdown formats."""

import os
import re

import click

from hord.org_parser import parse_org_file
from hord.md_parser import parse_md_file


def org_to_md(record) -> str:
    """Convert a parsed OrgRecord to markdown with YAML frontmatter."""
    lines = ["---"]

    if record.uuid:
        lines.append(f"id: {record.uuid}")
    if record.entity_type:
        lines.append(f"type: {record.entity_type}")
    if record.title:
        # Strip type suffix for cleaner markdown title
        lines.append(f"title: {record.title}")
    if record.created:
        lines.append(f"created: {record.created}")
    if record.geo:
        lines.append(f"geo: {record.geo}")

    lines.append("license: MIT/CC BY-SA 4.0")

    # Relations
    if record.relations:
        lines.append("relations:")
        for rel in record.relations:
            if rel.target_uuid:
                lines.append(f"  - \"{rel.rel_type}: {rel.target_uuid}  # {rel.target_label}\"")
            else:
                lines.append(f"  - \"{rel.rel_type}: {rel.target_label}\"")

    # Aliases
    if record.aliases:
        lines.append("aliases:")
        for alias in record.aliases:
            lines.append(f"  - \"{alias}\"")

    lines.append("---")
    lines.append("")

    # Title as H1
    if record.title:
        lines.append(f"# {record.title}")
        lines.append("")

    # Extract body content from the org file
    if record.filepath:
        body = _extract_org_body(record.filepath)
        if body:
            lines.append(body)

    return "\n".join(lines) + "\n"


def md_to_org(record) -> str:
    """Convert a parsed OrgRecord (from markdown) to org-mode format."""
    lines = [
        "#   -*- mode: org; fill-column: 60 -*-",
        "#+STARTUP: showall",
    ]

    title = record.title or "Untitled"
    lines.append(f"#+TITLE:   {title}")

    # Filetags
    tags = record.filetags if record.filetags else []
    if not tags and record.entity_type:
        # Derive tag from type
        type_to_tag = {
            "wh:con": "concept", "wh:pat": "pattern",
            "wh:key": "keystone", "wh:wrk": "work",
            "wh:per": "person", "wh:cat": "category",
            "wh:sys": "system", "wh:pla": "place",
            "wh:evt": "event", "wh:obj": "object",
            "wh:org": "organization",
        }
        tag = type_to_tag.get(record.entity_type, "concept")
        tags = ["hord", tag]
    filetags = " ".join(f'"{t}"' for t in tags)
    lines.append(f"#+FILETAGS: {filetags}")
    lines.append("")

    # H1 + property drawer
    lines.append(f"* {title}")
    lines.append("  :PROPERTIES:")
    if record.uuid:
        lines.append(f"  :ID:        {record.uuid}")
    if record.entity_type:
        lines.append(f"  :TYPE:      {record.entity_type}")
    if record.created:
        lines.append(f"  :CREATED:   {record.created}")
    if record.geo:
        lines.append(f"  :GEO:       {record.geo}")
    lines.append("  :LICENCE:   MIT/CC BY-SA 4.0")
    lines.append("  :END:")
    lines.append("")

    # Relations
    if record.relations:
        lines.append("** Relations")
        for rel in record.relations:
            if rel.target_uuid:
                lines.append(f"   - {rel.rel_type} :: [[id:{rel.target_uuid}][{rel.target_label}]]")
            else:
                lines.append(f"   - {rel.rel_type} :: {rel.target_label}")
        lines.append("")

    # Body
    lines.append("** Notes")
    lines.append("")
    if record.filepath:
        body = _extract_md_body(record.filepath)
        if body:
            lines.append(body)

    lines.append("")
    lines.append("** References")
    lines.append("")

    return "\n".join(lines) + "\n"


def _extract_org_body(filepath: str) -> str:
    """Extract the notes/content section from an org file."""
    with open(filepath, "r") as f:
        content = f.read()

    # Find ** Notes section and extract until ** References or end
    notes_match = re.search(r"^\*\* Notes\s*\n(.*?)(?=^\*\* |\Z)",
                            content, re.MULTILINE | re.DOTALL)
    if notes_match:
        body = notes_match.group(1).strip()
        if body:
            return body

    return ""


def _extract_md_body(filepath: str) -> str:
    """Extract the body content from a markdown file (after frontmatter and H1)."""
    with open(filepath, "r") as f:
        content = f.read()

    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + 4:]

    # Strip H1 title line
    lines = content.strip().split("\n")
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            start = i + 1
            break

    body = "\n".join(lines[start:]).strip()
    return body


@click.command("convert")
@click.argument("path")
@click.option("--to", "target_format", type=click.Choice(["md", "org"]),
              required=True, help="Target format")
@click.option("--output", "-o", default=None,
              help="Output directory (default: same directory)")
@click.option("--verbose", "-v", is_flag=True)
def convert_cmd(path, target_format, output, verbose):
    """Convert between org-mode and markdown formats.

    Converts a single file or all files in a directory.
    Metadata, relations, and aliases are preserved.
    """
    path = os.path.abspath(path)

    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        src_ext = ".md" if target_format == "org" else ".org"
        files = []
        for root, dirs, fnames in os.walk(path):
            for fname in sorted(fnames):
                if fname.endswith(src_ext) and not fname.startswith("."):
                    files.append(os.path.join(root, fname))
    else:
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(1)

    if not files:
        click.echo("No files to convert.")
        return

    converted = 0
    for fpath in files:
        # Parse source
        if fpath.endswith(".org"):
            record = parse_org_file(fpath)
            if not record.is_valid:
                if verbose:
                    click.echo(f"  Skipping {fpath} (no UUID)")
                continue
            result = org_to_md(record)
            new_ext = ".md"
        elif fpath.endswith(".md"):
            record = parse_md_file(fpath)
            if not record.is_valid:
                if verbose:
                    click.echo(f"  Skipping {fpath} (no UUID)")
                continue
            result = md_to_org(record)
            new_ext = ".org"
        else:
            continue

        # Determine output path
        basename = os.path.splitext(os.path.basename(fpath))[0] + new_ext
        if output:
            os.makedirs(output, exist_ok=True)
            out_path = os.path.join(output, basename)
        else:
            out_path = os.path.join(os.path.dirname(fpath), basename)

        with open(out_path, "w") as f:
            f.write(result)

        converted += 1
        if verbose:
            click.echo(f"  {fpath} → {out_path}")

    click.echo(f"Converted {converted} files to {target_format}")
