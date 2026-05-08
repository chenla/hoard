"""hord export — generate a browsable HTML site from a hord."""

import os
import re
from html import escape

import click

from hord.git_utils import find_hord_root
from hord.quad import read_quads, quad_path, read_all_quads
from hord.vocab import Vocabulary, find_vocab
from hord.query import load_index, find_incoming
from hord.holon import (
    find_expression_for, _get_card_type, _get_card_title,
    _is_expression_card,
)


# ── Styles ──────────────────────────────────────────────

CSS = """\
:root {
  --bg: #fafaf8;
  --fg: #2c2c2c;
  --accent: #2d6a4f;
  --border: #d4d4d0;
  --muted: #6b6b68;
  --link: #2d6a4f;
  --tag-bg: #e8e8e4;
  --card-bg: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a1a;
    --fg: #d4d4d0;
    --accent: #52b788;
    --border: #3a3a38;
    --muted: #9a9a96;
    --link: #52b788;
    --tag-bg: #2a2a28;
    --card-bg: #222220;
  }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: "IBM Plex Serif", Georgia, serif;
  background: var(--bg); color: var(--fg);
  max-width: 52rem; margin: 0 auto;
  padding: 2rem 1.5rem; line-height: 1.6;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 1.5rem; margin-bottom: .25rem; }
h2 { font-size: 1.1rem; color: var(--accent); margin: 1.5rem 0 .5rem; }
code {
  font-size: .75rem; word-break: break-all;
}
.subtitle {
  font-family: "IBM Plex Mono", monospace;
  font-size: .8rem; color: var(--muted); margin-bottom: 1.5rem;
}
.type-tag {
  display: inline-block; background: var(--tag-bg);
  padding: .1rem .5rem; border-radius: 3px;
  font-size: .8rem; font-family: "IBM Plex Mono", monospace;
}
.quad-table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
.quad-table td {
  padding: .35rem .5rem; border-bottom: 1px solid var(--border);
  font-size: .9rem; vertical-align: top;
}
.quad-table td:first-child {
  font-family: "IBM Plex Mono", monospace;
  font-size: .8rem; color: var(--muted);
  white-space: nowrap; width: 10rem; text-align: right;
  padding-right: 1rem;
}
.strata-section { border-left: 3px solid var(--accent); padding-left: 1rem; }
.incoming { color: var(--muted); font-size: .85rem; }
.incoming a { color: var(--link); }
.incoming > div { padding: .2rem 0; }
.notes {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 4px; padding: 1rem 1.25rem; margin: .5rem 0;
  font-size: .95rem;
}
.notes p { margin-bottom: .75rem; }
.notes p:last-child { margin-bottom: 0; }
.index-group { margin-bottom: 1.5rem; }
.index-item {
  padding: .4rem 0; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: baseline;
  gap: .5rem;
}
.index-item a { flex: 1; min-width: 0; }
.index-item .type-tag { font-size: .75rem; flex-shrink: 0; }
nav { margin-bottom: 2rem; font-size: .9rem; }
nav a { margin-right: 1rem; }
.breadcrumb { font-size: .85rem; color: var(--muted); margin-bottom: 1rem; }
.breadcrumb a { color: var(--muted); }
footer {
  margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: .8rem; color: var(--muted);
}
@media (max-width: 600px) {
  body { padding: 1rem .75rem; }
  h1 { font-size: 1.25rem; }
  .quad-table td:first-child {
    width: auto; min-width: 5rem;
    font-size: .7rem;
  }
  .quad-table td { font-size: .85rem; padding: .3rem .25rem; }
  .index-item { flex-wrap: wrap; }
  .subtitle code { display: block; margin-top: .25rem; }
}
"""


# ── Helpers ─────────────────────────────────────────────

def _looks_like_uuid(s: str) -> bool:
    return len(s) == 36 and s.count("-") == 4


def _entity_filename(uuid: str) -> str:
    return f"{uuid}.html"


def _extract_notes(filepath: str) -> str:
    """Extract the Notes section body from an org or markdown file."""
    if not filepath or not os.path.exists(filepath):
        return ""

    with open(filepath, "r") as f:
        content = f.read()

    if filepath.endswith(".md"):
        return _extract_notes_md(content)
    return _extract_notes_org(content)


def _extract_notes_org(content: str) -> str:
    """Extract text between ** Notes and the next ** heading or EOF."""
    lines = content.split("\n")
    in_notes = False
    notes_lines = []

    for line in lines:
        if re.match(r"^\*\*\s+Notes", line):
            in_notes = True
            continue
        if in_notes:
            if re.match(r"^\*\*\s+", line):
                break
            notes_lines.append(line)

    text = "\n".join(notes_lines).strip()
    return text


def _extract_notes_md(content: str) -> str:
    """Extract body text after frontmatter and heading."""
    # Skip frontmatter
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + 4:]

    # Skip the first heading
    lines = content.split("\n")
    body_lines = []
    past_heading = False
    for line in lines:
        if not past_heading:
            if line.startswith("# "):
                past_heading = True
            continue
        body_lines.append(line)

    return "\n".join(body_lines).strip()


def _text_to_html(text: str) -> str:
    """Convert plain text paragraphs to HTML paragraphs."""
    if not text:
        return ""

    paragraphs = re.split(r"\n\s*\n", text)
    html_parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Escape HTML and wrap
        para = escape(para)
        # Collapse internal whitespace but preserve line structure
        para = re.sub(r"\n\s*", " ", para)
        html_parts.append(f"<p>{para}</p>")

    return "\n".join(html_parts)


def _html_page(title: str, body: str, breadcrumb: str = "") -> str:
    """Wrap body content in a full HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{breadcrumb}
{body}
<footer>Generated by Hoard</footer>
</body>
</html>
"""


# ── Entity page ────────────────────────────────────────

def render_entity_page(uuid: str, hord_root: str, vocab: Vocabulary,
                       index: dict, path_for_uuid: dict) -> str:
    """Render a single entity as an HTML page."""
    quads = read_all_quads(hord_root, uuid)

    if not quads:
        return ""

    # Extract title and type
    title = uuid
    entity_type = ""
    for q in quads:
        if q.predicate == "v:title":
            title = q.object
        elif q.predicate == "v:type":
            entity_type = q.object

    type_label = vocab.label(entity_type) if entity_type else ""

    # Separate structural and strata quads
    strata_preds = {"v:s-wo", "v:s-eo", "v:s-mo", "v:s-io", "v:s-type"}
    structural = []
    strata = []

    for q in quads:
        if q.predicate in ("v:title",):
            continue
        if q.predicate in strata_preds:
            strata.append(q)
        else:
            structural.append(q)

    # Build quad rows
    def quad_rows(qlist):
        rows = []
        for q in qlist:
            pred_label = vocab.label(q.predicate)
            if _looks_like_uuid(q.object):
                obj_title = _resolve_title(q.object, hord_root)
                obj_html = f'<a href="{_entity_filename(q.object)}">{escape(obj_title)}</a>'
            else:
                obj_html = escape(q.object)
            rows.append(f"<tr><td>{escape(pred_label)}</td><td>{obj_html}</td></tr>")
        return "\n".join(rows)

    body_parts = []

    # Header
    body_parts.append(f"<h1>{escape(title)}</h1>")
    subtitle = f'<span class="type-tag">{escape(type_label)}</span> '
    subtitle += f'<code>{uuid}</code>'
    body_parts.append(f'<div class="subtitle">{subtitle}</div>')

    # Structural relationships
    if structural:
        body_parts.append("<h2>Relationships</h2>")
        body_parts.append(f'<table class="quad-table">{quad_rows(structural)}</table>')

    # Strata (WEMI)
    if strata:
        body_parts.append('<h2>Strata (WEMI)</h2>')
        body_parts.append(f'<div class="strata-section"><table class="quad-table">{quad_rows(strata)}</table></div>')

    # Incoming links
    incoming = find_incoming(hord_root, uuid)
    if incoming:
        body_parts.append("<h2>Incoming Links</h2>")
        body_parts.append('<div class="incoming">')
        for q in incoming:
            pred_label = vocab.label(q.predicate)
            subj_title = _resolve_title(q.subject, hord_root)
            body_parts.append(
                f'<div><a href="{_entity_filename(q.subject)}">{escape(subj_title)}</a>'
                f' &larr; {escape(pred_label)}</div>'
            )
        body_parts.append("</div>")

    # Notes (from source file)
    source_path = path_for_uuid.get(uuid)
    if source_path:
        full_path = os.path.join(hord_root, source_path)
        notes_text = _extract_notes(full_path)
        if notes_text:
            notes_html = _text_to_html(notes_text)
            body_parts.append("<h2>Notes</h2>")
            body_parts.append(f'<div class="notes">{notes_html}</div>')

    breadcrumb = '<div class="breadcrumb"><a href="index.html">&larr; Index</a></div>'
    return _html_page(title, "\n".join(body_parts), breadcrumb)


def _resolve_title(uuid: str, hord_root: str) -> str:
    """Get the title for a UUID from its quads."""
    for q in read_all_quads(hord_root, uuid):
        if q.predicate == "v:title":
            return q.object
    return uuid[:8] + "…"


# ── Index page ─────────────────────────────────────────

def render_index_page(entities: list[dict], hord_name: str) -> str:
    """Render the index page listing all entities grouped by type."""

    # Group by type label
    groups: dict[str, list[dict]] = {}
    for ent in entities:
        type_label = ent.get("type_label", "Other")
        groups.setdefault(type_label, []).append(ent)

    body_parts = []
    body_parts.append(f"<h1>{escape(hord_name)}</h1>")
    body_parts.append(f'<div class="subtitle">{len(entities)} entities</div>')

    # Sort groups: put categories first, then alphabetical
    for group_name in sorted(groups.keys()):
        items = sorted(groups[group_name], key=lambda e: e["title"].lower())
        body_parts.append(f'<div class="index-group">')
        body_parts.append(f"<h2>{escape(group_name)} ({len(items)})</h2>")
        for item in items:
            body_parts.append(
                f'<div class="index-item">'
                f'<a href="{_entity_filename(item["uuid"])}">{escape(item["title"])}</a>'
                f'<span class="type-tag">{escape(item["type_label"])}</span>'
                f'</div>'
            )
        body_parts.append("</div>")

    return _html_page(hord_name, "\n".join(body_parts))


# ── Holon page ────────────────────────────────────────

HOLON_CSS_EXTRA = """\
.holon-header { margin-bottom: 2rem; }
.holon-meta { font-size: .9rem; color: var(--muted); margin: .25rem 0; }
.holon-member {
  border: 1px solid var(--border); border-radius: 4px;
  padding: 1rem 1.25rem; margin-bottom: 1rem;
  background: var(--card-bg);
}
.holon-member h3 { font-size: 1.05rem; margin-bottom: .25rem; }
.holon-member h3 a { color: var(--fg); }
.holon-member .member-meta {
  font-size: .8rem; color: var(--muted); margin-bottom: .5rem;
}
.holon-member .member-meta .type-tag { font-size: .75rem; }
.holon-member .member-notes { font-size: .9rem; }
.holon-member .member-notes p { margin-bottom: .5rem; }
.holon-member .member-notes p:last-child { margin-bottom: 0; }
.expr-badge {
  display: inline-block; background: var(--accent); color: #fff;
  padding: .05rem .4rem; border-radius: 3px; font-size: .7rem;
  margin-left: .5rem; vertical-align: middle;
}
.whole-link {
  font-size: .8rem; color: var(--muted); margin-left: .5rem;
}
.debate-section { margin-top: 2rem; }
.debate-section h2 { border-bottom: 2px solid var(--accent); padding-bottom: .25rem; }
"""


def render_holon_page(holon_uuid: str, hord_root: str, vocab: Vocabulary,
                      path_for_uuid: dict) -> str:
    """Render a holon as an HTML landing page with member cards."""
    holon_quads = read_all_quads(hord_root, holon_uuid)

    # Extract holon metadata
    holon_title = holon_uuid
    expr_prefer = None
    members = {}
    order_map = {}

    for q in holon_quads:
        if q.predicate == "v:title":
            holon_title = q.object
        elif q.predicate == "v:h-expr":
            expr_prefer = q.object
        elif q.predicate == "v:h-member":
            members[q.object] = 999
        elif q.predicate == "v:h-order":
            try:
                order_map[q.subject] = int(q.object)
            except ValueError:
                pass

    for m_uuid, pos in order_map.items():
        if m_uuid in members:
            members[m_uuid] = pos

    ordered = sorted(members.items(), key=lambda x: (x[1], x[0]))

    # Extract holon description from source file
    holon_desc = ""
    source_path = path_for_uuid.get(holon_uuid)
    if source_path:
        full_path = os.path.join(hord_root, source_path)
        holon_desc = _extract_holon_description(full_path)

    # Build page
    body_parts = []
    body_parts.append('<div class="holon-header">')
    body_parts.append(f"<h1>{escape(holon_title)}</h1>")
    if holon_desc:
        body_parts.append(f"<p>{escape(holon_desc)}</p>")
    body_parts.append(f'<div class="holon-meta">{len(members)} members')
    if expr_prefer:
        body_parts.append(f' &middot; Expression: <em>{escape(expr_prefer)}</em>')
    body_parts.append("</div>")
    body_parts.append("</div>")

    # Group members by type for rendering
    type_order = ["wh:evt", "wh:per", "wh:org", "wh:media"]
    type_groups: dict[str, list] = {}

    for m_uuid, pos in ordered:
        m_type = _get_card_type(hord_root, m_uuid) or "other"
        if m_type not in type_groups:
            type_groups[m_type] = []

        # Resolve expression
        display_uuid = m_uuid
        is_expr = False
        if expr_prefer:
            expr_uuid = find_expression_for(hord_root, m_uuid, expr_prefer)
            if expr_uuid:
                display_uuid = expr_uuid
                is_expr = True

        display_title = _resolve_title(display_uuid, hord_root)
        whole_title = _resolve_title(m_uuid, hord_root) if is_expr else None

        # Get notes from source file
        notes_path = path_for_uuid.get(display_uuid)
        notes_text = ""
        if notes_path:
            full_path = os.path.join(hord_root, notes_path)
            notes_text = _extract_notes(full_path)

        type_groups[m_type].append({
            "uuid": display_uuid,
            "whole_uuid": m_uuid if is_expr else None,
            "title": display_title,
            "whole_title": whole_title,
            "type": m_type,
            "type_label": vocab.label(m_type) if m_type else "Other",
            "notes": notes_text,
            "is_expr": is_expr,
            "pos": pos,
        })

    # Render groups in type order
    for t in type_order:
        if t not in type_groups:
            continue
        group = type_groups[t]
        type_label = vocab.label(t) if t else "Other"

        body_parts.append(f'<div class="debate-section">')
        body_parts.append(f"<h2>{escape(type_label)}s</h2>")

        for member in group:
            body_parts.append(_render_member_card(member))

        body_parts.append("</div>")

    # Any remaining types not in type_order
    for t, group in type_groups.items():
        if t in type_order:
            continue
        type_label = vocab.label(t) if t else "Other"
        body_parts.append(f'<div class="debate-section">')
        body_parts.append(f"<h2>{escape(type_label)}</h2>")
        for member in group:
            body_parts.append(_render_member_card(member))
        body_parts.append("</div>")

    breadcrumb = '<div class="breadcrumb"><a href="index.html">&larr; Index</a></div>'

    # Use extended CSS
    page_css = CSS + HOLON_CSS_EXTRA
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(holon_title)}</title>
<style>{page_css}</style>
</head>
<body>
{breadcrumb}
{chr(10).join(body_parts)}
<footer>Generated by Hoard</footer>
</body>
</html>
"""


def _render_member_card(member: dict) -> str:
    """Render a single member as an HTML card."""
    parts = []
    parts.append('<div class="holon-member">')

    # Title with link
    title_html = f'<a href="{_entity_filename(member["uuid"])}">{escape(member["title"])}</a>'
    if member["is_expr"]:
        title_html += '<span class="expr-badge">expression</span>'
    if member["whole_uuid"]:
        title_html += (f'<a class="whole-link" '
                       f'href="{_entity_filename(member["whole_uuid"])}">'
                       f'(← {escape(member["whole_title"] or "Whole")})</a>')
    parts.append(f"<h3>{title_html}</h3>")

    # Type
    parts.append(f'<div class="member-meta">'
                 f'<span class="type-tag">{escape(member["type_label"])}</span>'
                 f'</div>')

    # Notes
    if member["notes"]:
        notes_html = _text_to_html(member["notes"])
        parts.append(f'<div class="member-notes">{notes_html}</div>')

    parts.append("</div>")
    return "\n".join(parts)


def _extract_holon_description(filepath: str) -> str:
    """Extract the description text between the properties and first heading."""
    if not filepath or not os.path.exists(filepath):
        return ""
    with open(filepath, "r") as f:
        content = f.read()
    lines = content.split("\n")
    desc_lines = []
    past_props = False
    for line in lines:
        if line.strip() == ":END:":
            past_props = True
            continue
        if past_props:
            if re.match(r"^\*{1,3}\s+", line):
                break
            stripped = line.strip()
            if stripped:
                desc_lines.append(stripped)
    return " ".join(desc_lines)


# ── CLI command ────────────────────────────────────────

@click.command("export")
@click.option("--output", "-o", default="_site",
              help="Output directory (default: _site/)")
@click.option("--holon", "holon_name", default=None,
              help="Export a holon as a landing page with member cards")
def export_cmd(output, holon_name):
    """Export the hord as a browsable HTML site.

    Generates one HTML page per entity plus an index page.
    All pages are self-contained with inline CSS — no
    external dependencies.

    With --holon, also generates a holon landing page that
    shows all members with expression substitution and
    inline notes.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    # Load vocab
    vocab_path = find_vocab(hord_root)
    if not vocab_path:
        click.echo("Error: no vocabulary found.", err=True)
        raise SystemExit(1)
    vocab = Vocabulary.load(vocab_path)

    # Load index and build path→uuid and uuid→path maps
    index = load_index(hord_root)
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    path_for_uuid: dict[str, str] = {}
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                path_for_uuid[parts[1]] = parts[0]

    # Collect all entities
    entities = []
    seen = set()
    for key, uuid in index.items():
        if uuid in seen:
            continue
        seen.add(uuid)

        quads = read_all_quads(hord_root, uuid)
        if not quads:
            continue

        title = uuid
        etype = ""
        for q in quads:
            if q.predicate == "v:title":
                title = q.object
            elif q.predicate == "v:type":
                etype = q.object

        type_label = vocab.label(etype) if etype else "Other"
        entities.append({
            "uuid": uuid,
            "title": title,
            "type": etype,
            "type_label": type_label,
        })

    if not entities:
        click.echo("No entities found. Run 'hord compile' first.")
        return

    # Create output directory
    out_dir = os.path.join(hord_root, output)
    os.makedirs(out_dir, exist_ok=True)

    # Read hord name from config
    hord_name = "Hord"
    config_path = os.path.join(hord_root, ".hord", "config.toml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            for line in f:
                if line.strip().startswith("name"):
                    match = re.search(r'"(.+)"', line)
                    if match:
                        hord_name = match.group(1)
                        break

    # Render index
    index_html = render_index_page(entities, hord_name)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(index_html)

    # Render entity pages
    for ent in entities:
        page = render_entity_page(ent["uuid"], hord_root, vocab, index, path_for_uuid)
        if page:
            with open(os.path.join(out_dir, _entity_filename(ent["uuid"])), "w") as f:
                f.write(page)

    # Render holon page if requested
    if holon_name:
        holon_uuid = index.get(holon_name)
        if holon_uuid is None:
            # Try partial match
            for key, val in index.items():
                if key.startswith(holon_name) and len(holon_name) >= 4:
                    holon_uuid = val
                    break
        if holon_uuid is None:
            click.echo(f"Warning: holon '{holon_name}' not found, skipping holon page.", err=True)
        else:
            holon_html = render_holon_page(holon_uuid, hord_root, vocab, path_for_uuid)
            holon_filename = f"holon-{holon_uuid}.html"
            with open(os.path.join(out_dir, holon_filename), "w") as f:
                f.write(holon_html)
            # Also write as holon.html for easy access
            with open(os.path.join(out_dir, "holon.html"), "w") as f:
                f.write(holon_html)
            click.echo(f"Holon page: {os.path.join(out_dir, 'holon.html')}")

    click.echo(f"Exported {len(entities)} entities to {out_dir}/")
    click.echo(f"  Open {os.path.join(out_dir, 'index.html')} to browse.")
