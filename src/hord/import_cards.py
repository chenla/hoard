"""hord import — import notes from other PKM systems into a hord.

Supported sources (auto-detected or explicit):
  - plain markdown (files with optional YAML frontmatter)
  - obsidian (markdown vault with [[wikilinks]])
  - org-roam (org files with :ID: properties)
  - dendron (dot-hierarchy filenames, YAML frontmatter with id)
  - logseq (outliner markdown/org with prop:: value syntax)
  - notion (exported markdown with UUID-suffixed filenames)
"""

import os
import re
import uuid
from datetime import datetime, timezone

import click

from hord.git_utils import find_hord_root, read_config
from hord.new import TYPE_SHORTCUTS, TYPE_SUFFIX, slugify


# ── Source detection ─────────────────────────────────────

def detect_source(path: str) -> str:
    """Auto-detect which PKM system a directory came from."""
    if os.path.isdir(os.path.join(path, ".obsidian")):
        return "obsidian"
    if os.path.isdir(os.path.join(path, "logseq")):
        return "logseq"
    if os.path.isdir(os.path.join(path, ".dendron")):
        return "dendron"

    # Check file patterns
    files = _collect_files(path)
    if not files:
        return "markdown"

    # Notion: UUID-suffixed filenames like "Page Name a1b2c3d4.md"
    notion_pat = re.compile(r" [0-9a-f]{32}\.md$")
    if any(notion_pat.search(f) for f in files[:20]):
        return "notion"

    # Dendron: flat files with dot-hierarchy names
    basenames = [os.path.basename(f) for f in files[:30]]
    dot_count = sum(1 for b in basenames if b.count(".") >= 3)
    if dot_count > len(basenames) * 0.5:
        return "dendron"

    # org-roam: org files with :ID: in property drawers
    org_files = [f for f in files if f.endswith(".org")]
    if org_files:
        roam_count = 0
        for f in org_files[:10]:
            try:
                with open(f) as fh:
                    head = fh.read(2048)
                if ":ID:" in head and "#+title" in head.lower():
                    roam_count += 1
            except (OSError, UnicodeDecodeError):
                pass
        if roam_count > len(org_files[:10]) * 0.5:
            return "org-roam"

    # Logseq: check for prop:: value syntax in first few files
    md_files = [f for f in files if f.endswith(".md")]
    if md_files:
        logseq_count = 0
        prop_pat = re.compile(r"^[a-z_-]+:: ", re.MULTILINE)
        for f in md_files[:10]:
            try:
                with open(f) as fh:
                    head = fh.read(2048)
                if prop_pat.search(head):
                    logseq_count += 1
            except (OSError, UnicodeDecodeError):
                pass
        if logseq_count > len(md_files[:10]) * 0.5:
            return "logseq"

    # Obsidian without .obsidian dir: check for [[wikilinks]]
    wikilink_pat = re.compile(r"\[\[[^\]]+\]\]")
    for f in md_files[:10]:
        try:
            with open(f) as fh:
                content = fh.read(4096)
            if wikilink_pat.search(content):
                return "obsidian"
        except (OSError, UnicodeDecodeError):
            pass

    return "markdown"


def _collect_files(path: str) -> list:
    """Collect importable files from a directory."""
    result = []
    for root, dirs, fnames in os.walk(path):
        # Skip hidden dirs and common config dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("logseq", "node_modules", "__pycache__")]
        for fname in sorted(fnames):
            if fname.startswith(".") or fname.startswith("#"):
                continue
            if fname.endswith((".md", ".org")):
                result.append(os.path.join(root, fname))
    return result


# ── YAML frontmatter parser (minimal, no dependency) ────

def _parse_yaml_frontmatter(text: str) -> tuple:
    """Parse YAML frontmatter from markdown text.

    Returns (metadata_dict, body_text).  Handles simple
    key: value pairs and lists.  Not a full YAML parser.
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[4:end]
    body = text[end + 4:].strip()
    meta = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item
        if stripped.startswith("- ") and current_key:
            val = stripped[2:].strip().strip('"').strip("'")
            if current_list is None:
                current_list = []
                meta[current_key] = current_list
            current_list.append(val)
            continue

        # Key: value
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)", line)
        if m:
            current_key = m.group(1).lower()
            val = m.group(2).strip().strip('"').strip("'")
            current_list = None
            if val and val != "[]":
                meta[current_key] = val
            elif val == "[]":
                meta[current_key] = []
            # else: might be a list starting on the next line
            continue

    return meta, body


# ── Logseq property parser ──────────────────────────────

def _parse_logseq_props(text: str) -> tuple:
    """Parse Logseq prop:: value lines from the start of text.

    Returns (metadata_dict, body_text).
    """
    meta = {}
    lines = text.split("\n")
    body_start = 0
    prop_pat = re.compile(r"^([a-z_-]+)::\s*(.*)")

    for i, line in enumerate(lines):
        m = prop_pat.match(line.strip("- ").strip())
        if m and i < 20:  # props only at the top
            key = m.group(1).lower().replace("-", "_")
            val = m.group(2).strip()
            meta[key] = val
            body_start = i + 1
        elif line.strip() == "" and i < 3:
            body_start = i + 1
        elif meta:
            break

    body = "\n".join(lines[body_start:]).strip()
    return meta, body


# ── Link converters ──────────────────────────────────────

def _convert_wikilinks(text: str, link_map: dict) -> str:
    """Convert [[wikilinks]] to hord id: links or plain text.

    link_map maps normalized titles to UUIDs.
    """
    def _replace(m):
        inner = m.group(1)
        # [[target|display]] or [[target]]
        if "|" in inner:
            target, display = inner.split("|", 1)
        else:
            target = inner
            display = inner

        # Strip heading/block refs
        target = target.split("#")[0].strip()
        norm = target.lower().replace(" ", "_").replace("-", "_")

        uid = link_map.get(norm)
        if uid:
            return f"[[id:{uid}][{display}]]"
        return display

    return re.sub(r"\[\[([^\]]+)\]\]", _replace, text)


def _convert_md_links_to_org(text: str) -> str:
    """Convert standard [text](path.md) links to plain references."""
    def _replace(m):
        display = m.group(1)
        return display

    return re.sub(r"\[([^\]]+)\]\([^)]+\.md[^)]*\)", _replace, text)


def _strip_logseq_bullets(text: str) -> str:
    """Convert Logseq outliner bullets to normal paragraphs.

    Logseq stores everything as `- ` prefixed bullets.
    Nested bullets get extra indentation.  We flatten the
    top-level bullets to paragraphs and keep nested ones
    as indented list items.
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("- ") and indent == 0:
            # Top-level bullet → paragraph
            result.append(stripped[2:])
        elif stripped.startswith("- ") and indent > 0:
            # Nested bullet → indented list item
            result.append(line)
        else:
            result.append(line)
    return "\n".join(result)


# ── Notion filename cleaner ──────────────────────────────

_NOTION_UUID_PAT = re.compile(r"\s+[0-9a-f]{32}$")


def _clean_notion_title(filename: str) -> str:
    """Strip Notion's UUID suffix from a filename."""
    name = os.path.splitext(filename)[0]
    return _NOTION_UUID_PAT.sub("", name).strip()


# ── Dendron hierarchy parser ─────────────────────────────

def _dendron_title_from_filename(filename: str) -> str:
    """Derive a title from Dendron's dot-hierarchy filename.

    e.g. 'project.designs.promotion.md' → 'Promotion'
    """
    name = os.path.splitext(filename)[0]
    parts = name.split(".")
    return parts[-1].replace("-", " ").title()


# ── Core import logic ────────────────────────────────────

def _make_timestamp() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%dT%H:%M")


def _guess_type_from_tags(tags: list) -> str:
    """Try to infer hord entity type from tags."""
    tag_set = {t.lower() for t in tags}
    if tag_set & {"person", "people", "bio", "biography"}:
        return "wh:per"
    if tag_set & {"book", "paper", "article", "work", "reference"}:
        return "wh:wrk"
    if tag_set & {"place", "location", "city", "country"}:
        return "wh:pla"
    if tag_set & {"event", "meeting", "conference"}:
        return "wh:event"
    if tag_set & {"project", "system"}:
        return "wh:sys"
    if tag_set & {"org", "organization", "company", "institution"}:
        return "wh:org"
    return "wh:con"


def import_file(filepath: str, source_type: str, fmt: str,
                link_map: dict, timestamp: str) -> tuple:
    """Import a single file and return (filename, content, title).

    Returns (None, None, None) if the file should be skipped.
    """
    try:
        with open(filepath) as f:
            raw = f.read()
    except (OSError, UnicodeDecodeError):
        return None, None, None

    if not raw.strip():
        return None, None, None

    # ── Parse metadata by source type ────────────────────
    meta = {}
    body = raw
    title = None
    tags = []
    aliases = []
    existing_uuid = None

    if source_type == "org-roam":
        return _import_org_roam(filepath, raw, fmt, timestamp)

    if source_type == "logseq":
        meta, body = _parse_logseq_props(raw)
        body = _strip_logseq_bullets(body)
        title = meta.get("title")
        tags_str = meta.get("tags", "")
        if isinstance(tags_str, str) and tags_str:
            tags = [t.strip().strip("#") for t in tags_str.split(",")]
        aliases_str = meta.get("alias", "")
        if isinstance(aliases_str, str) and aliases_str:
            aliases = [a.strip() for a in aliases_str.split(",")]

    elif source_type == "notion":
        meta, body = _parse_yaml_frontmatter(raw)
        basename = os.path.basename(filepath)
        title = _clean_notion_title(basename)
        if isinstance(meta.get("tags"), list):
            tags = meta["tags"]

    elif source_type == "dendron":
        meta, body = _parse_yaml_frontmatter(raw)
        existing_uuid = meta.get("id")
        title = meta.get("title")
        if not title:
            title = _dendron_title_from_filename(os.path.basename(filepath))
        if isinstance(meta.get("tags"), list):
            tags = meta["tags"]

    else:
        # obsidian or plain markdown
        meta, body = _parse_yaml_frontmatter(raw)
        title = meta.get("title")
        existing_uuid = meta.get("id")
        if isinstance(meta.get("tags"), list):
            tags = meta["tags"]
        elif isinstance(meta.get("tags"), str):
            tags = [t.strip() for t in meta["tags"].split(",")]
        if isinstance(meta.get("aliases"), list):
            aliases = meta["aliases"]

    # Fall back to H1 or filename for title
    if not title:
        h1 = re.search(r"^#\s+(.+)", body, re.MULTILINE)
        if h1:
            title = h1.group(1).strip()
            # Remove the H1 from body since we'll regenerate it
            body = body[:h1.start()] + body[h1.end():]
        else:
            title = os.path.splitext(os.path.basename(filepath))[0]
            title = title.replace("_", " ").replace("-", " ").strip()

    if not title:
        return None, None, None

    # Convert wikilinks if present
    if source_type in ("obsidian", "logseq"):
        body = _convert_wikilinks(body, link_map)
    else:
        body = _convert_md_links_to_org(body)

    # Strip any remaining H1 from body (we regenerate it)
    body = re.sub(r"^#\s+.*\n?", "", body, count=1).strip()

    # Determine entity type
    entity_type = _guess_type_from_tags(tags)

    # Use existing UUID or generate new one
    card_uuid = existing_uuid or str(uuid.uuid4())
    suffix = TYPE_SUFFIX.get(entity_type, "4")
    slug = slugify(title)
    display_title = f"{title}\u2014{suffix}"

    if fmt == "org":
        content = _build_org_card(card_uuid, entity_type, display_title,
                                  timestamp, tags, aliases, body)
        filename = f"{slug}--{suffix}.org"
    else:
        content = _build_md_card(card_uuid, entity_type, display_title,
                                 timestamp, tags, aliases, body)
        filename = f"{slug}--{suffix}.md"

    return filename, content, title


def _import_org_roam(filepath: str, raw: str, fmt: str,
                     timestamp: str) -> tuple:
    """Import an org-roam file, preserving its structure."""
    # Extract metadata from property drawer and keywords
    uid = None
    title = None
    tags = []

    # File-level :ID:
    id_match = re.search(r":ID:\s+(\S+)", raw[:1024])
    if id_match:
        uid = id_match.group(1)
    else:
        uid = str(uuid.uuid4())

    title_match = re.search(r"#\+(?:title|TITLE):\s+(.+)", raw)
    if title_match:
        title = title_match.group(1).strip()

    tags_match = re.search(r"#\+(?:filetags|FILETAGS):\s+(.+)", raw)
    if tags_match:
        tag_str = tags_match.group(1).strip().strip(":")
        tags = [t for t in tag_str.split(":") if t]

    if not title:
        return None, None, None

    # Extract body (everything after properties and keywords)
    body_start = 0
    lines = raw.split("\n")
    in_props = False
    for i, line in enumerate(lines):
        if ":PROPERTIES:" in line:
            in_props = True
        elif ":END:" in line and in_props:
            in_props = False
            continue
        elif line.startswith("#+"):
            continue
        elif line.startswith("* ") and i < 10:
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()

    # Remove org-roam subsection headers we'll regenerate
    body = re.sub(r"^\*\* Relations\s*\n", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\*\* Notes\s*\n", "", body, flags=re.MULTILINE)
    body = re.sub(r"^\*\* References\s*\n", "", body, flags=re.MULTILINE)

    entity_type = _guess_type_from_tags(tags)
    suffix = TYPE_SUFFIX.get(entity_type, "4")
    slug = slugify(title)
    display_title = f"{title}\u2014{suffix}"

    if fmt == "org":
        content = _build_org_card(uid, entity_type, display_title,
                                  timestamp, tags, [], body)
        filename = f"{slug}--{suffix}.org"
    else:
        content = _build_md_card(uid, entity_type, display_title,
                                 timestamp, tags, [], body)
        filename = f"{slug}--{suffix}.md"

    return filename, content, title


# ── Card builders ────────────────────────────────────────

def _build_org_card(card_uuid: str, entity_type: str,
                    display_title: str, timestamp: str,
                    tags: list, aliases: list, body: str) -> str:
    """Build an org-mode hord card."""
    filetags = ["hord"]
    type_tag_map = {
        "wh:con": "concept", "wh:pat": "pattern", "wh:key": "keystone",
        "wh:wrk": "work", "wh:per": "person", "wh:cat": "category",
        "wh:sys": "system", "wh:pla": "place", "wh:evt": "event",
        "wh:obj": "object", "wh:org": "organization",
    }
    filetags.append(type_tag_map.get(entity_type, "concept"))
    ft_str = " ".join(f'"{t}"' for t in filetags)

    props = [
        "  :PROPERTIES:",
        f"  :ID:        {card_uuid}",
        f"  :TYPE:      {entity_type}",
        f"  :CREATED:   {timestamp}",
    ]
    if aliases:
        alias_str = " ".join(f'"{a}"' for a in aliases)
        props.append(f"  :ROAM_ALIASES: {alias_str}")
    if tags:
        props.append(f"  :TAGS:      {' '.join(tags)}")
    props.append("  :LICENCE:   MIT/CC BY-SA 4.0")
    props.append("  :END:")

    lines = [
        "#   -*- mode: org; fill-column: 60 -*-",
        "#+STARTUP: showall",
        f"#+TITLE:   {display_title}",
        f"#+FILETAGS: {ft_str}",
        "",
        f"* {display_title}",
        *props,
        "",
        "** Relations",
        f"   - PT :: {display_title}",
    ]

    if aliases:
        for alias in aliases:
            lines.append(f"   - UF :: {alias}")
    lines.append("")

    lines.append("** Notes")
    lines.append("")
    if body:
        lines.append(body)
        lines.append("")

    lines.append("** References")
    lines.append("")

    return "\n".join(lines)


def _build_md_card(card_uuid: str, entity_type: str,
                   display_title: str, timestamp: str,
                   tags: list, aliases: list, body: str) -> str:
    """Build a markdown hord card."""
    lines = [
        "---",
        f"id: {card_uuid}",
        f"type: {entity_type}",
        f"title: {display_title}",
        f"created: {timestamp}",
        "license: MIT/CC BY-SA 4.0",
    ]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - \"{t}\"")
    if aliases:
        lines.append("aliases:")
        for a in aliases:
            lines.append(f"  - \"{a}\"")
    lines.append("relations:")
    lines.append(f"  - \"PT: {display_title}\"")
    if aliases:
        for alias in aliases:
            lines.append(f"  - \"UF: {alias}\"")
    lines.append("---")
    lines.append("")
    lines.append(f"# {display_title}")
    lines.append("")
    if body:
        lines.append(body)
        lines.append("")

    return "\n".join(lines)


# ── First pass: build link map ───────────────────────────

def build_link_map(files: list, source_type: str) -> dict:
    """Build a map from normalized titles to UUIDs.

    First pass: read all files, extract or generate UUIDs,
    map their titles so cross-references can be resolved.
    """
    link_map = {}
    uuid_map = {}  # filepath → uuid

    for fpath in files:
        try:
            with open(fpath) as f:
                head = f.read(2048)
        except (OSError, UnicodeDecodeError):
            continue

        title = None
        uid = None

        if source_type == "org-roam":
            id_m = re.search(r":ID:\s+(\S+)", head)
            if id_m:
                uid = id_m.group(1)
            title_m = re.search(r"#\+(?:title|TITLE):\s+(.+)", head)
            if title_m:
                title = title_m.group(1).strip()

        elif source_type == "logseq":
            prop_m = re.search(r"^title::\s*(.*)", head, re.MULTILINE)
            if prop_m:
                title = prop_m.group(1).strip()

        elif source_type == "dendron":
            meta, _ = _parse_yaml_frontmatter(head)
            uid = meta.get("id")
            title = meta.get("title")
            if not title:
                title = _dendron_title_from_filename(os.path.basename(fpath))

        elif source_type == "notion":
            title = _clean_notion_title(os.path.basename(fpath))

        else:
            meta, body = _parse_yaml_frontmatter(head)
            uid = meta.get("id")
            title = meta.get("title")
            if not title:
                h1 = re.search(r"^#\s+(.+)", body if body else head,
                               re.MULTILINE)
                if h1:
                    title = h1.group(1).strip()

        if not title:
            title = os.path.splitext(os.path.basename(fpath))[0]
            title = title.replace("_", " ").replace("-", " ")

        if not uid:
            uid = str(uuid.uuid4())

        uuid_map[fpath] = uid
        norm = title.lower().replace(" ", "_").replace("-", "_")
        link_map[norm] = uid

    return link_map


# ── CLI command ──────────────────────────────────────────

@click.command("import")
@click.argument("path")
@click.option("--from", "source_type",
              type=click.Choice(["auto", "markdown", "obsidian",
                                 "org-roam", "dendron", "logseq",
                                 "notion"]),
              default="auto",
              help="Source format (default: auto-detect)")
@click.option("--format", "-f", "fmt",
              type=click.Choice(["org", "md"]),
              default=None,
              help="Output format (default: from config.toml)")
@click.option("--dir", "-d", "content_dir", default="content",
              help="Content directory (default: content/)")
@click.option("--dry-run", is_flag=True,
              help="Show what would be imported without writing files")
@click.option("--verbose", "-v", is_flag=True)
def import_cmd(path, source_type, fmt, content_dir, dry_run, verbose):
    """Import notes from another PKM system.

    PATH is the directory (or single file) to import from.
    Source format is auto-detected from directory structure
    but can be overridden with --from.

    Examples:

        hord import ~/Documents/obsidian-vault

        hord import ~/org-roam/ --from org-roam

        hord import ./exported-notion --from notion -f md

        hord import ~/notes --dry-run
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord. Run 'hord init' first.",
                    err=True)
        raise SystemExit(1)

    path = os.path.abspath(path)
    if not os.path.exists(path):
        click.echo(f"Error: path does not exist: {path}", err=True)
        raise SystemExit(1)

    # Default format from config
    if fmt is None:
        config = read_config(hord_root)
        fmt = config.get("format", "org")

    # Collect files
    if os.path.isfile(path):
        files = [path]
        if source_type == "auto":
            source_type = "markdown"
    else:
        if source_type == "auto":
            source_type = detect_source(path)
        files = _collect_files(path)

    if not files:
        click.echo("No importable files found.")
        return

    click.echo(f"Detected source: {source_type}")
    click.echo(f"Found {len(files)} files to import")

    # First pass: build cross-reference map
    if verbose:
        click.echo("Building link map...")
    link_map = build_link_map(files, source_type)

    # Second pass: import each file
    timestamp = _make_timestamp()
    out_dir = os.path.join(hord_root, content_dir)
    if not dry_run:
        os.makedirs(out_dir, exist_ok=True)

    imported = 0
    skipped = 0
    collisions = 0

    for fpath in files:
        filename, content, title = import_file(
            fpath, source_type, fmt, link_map, timestamp)

        if filename is None:
            skipped += 1
            if verbose:
                click.echo(f"  SKIP  {os.path.basename(fpath)}")
            continue

        out_path = os.path.join(out_dir, filename)

        # Handle filename collisions
        if os.path.exists(out_path):
            base, ext = os.path.splitext(filename)
            counter = 2
            while os.path.exists(out_path):
                out_path = os.path.join(out_dir, f"{base}_{counter}{ext}")
                counter += 1
            collisions += 1

        if dry_run:
            click.echo(f"  WOULD IMPORT  {title}")
            if verbose:
                click.echo(f"                → {filename}")
        else:
            with open(out_path, "w") as f:
                f.write(content)
            imported += 1
            if verbose:
                click.echo(f"  OK  {title} → {filename}")

    click.echo("")
    if dry_run:
        click.echo(f"Dry run: {imported + len(files) - skipped} "
                    f"would be imported, {skipped} skipped")
    else:
        click.echo(f"Imported {imported} cards into {content_dir}/")
        if skipped:
            click.echo(f"Skipped {skipped} files (empty or unparseable)")
        if collisions:
            click.echo(f"Renamed {collisions} files to avoid collisions")
        click.echo("")
        click.echo("Next steps:")
        click.echo("  hord compile    # generate quads from imported cards")
        click.echo("  hord status     # review what was imported")
