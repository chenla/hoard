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
  font-size: 1.25rem;
  background: var(--bg); color: var(--fg);
  max-width: 52rem; margin: 0 auto;
  padding: 2.5rem 1.5rem; line-height: 1.75;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 2rem; margin-bottom: .35rem; }
h2 { font-size: 1.4rem; color: var(--accent); margin: 1.75rem 0 .5rem; }
code {
  font-size: .9rem; word-break: break-all;
}
.subtitle {
  font-family: "IBM Plex Mono", monospace;
  font-size: 1rem; color: var(--muted); margin-bottom: 1.5rem;
}
.type-tag {
  display: inline-block; background: var(--tag-bg);
  padding: .2rem .6rem; border-radius: 3px;
  font-size: .9rem; font-family: "IBM Plex Mono", monospace;
}
.quad-table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
.quad-table td {
  padding: .45rem .6rem; border-bottom: 1px solid var(--border);
  font-size: 1.1rem; vertical-align: top;
}
.quad-table td:first-child {
  font-family: "IBM Plex Mono", monospace;
  font-size: .9rem; color: var(--muted);
  white-space: nowrap; width: 10rem; text-align: right;
  padding-right: 1rem;
}
.strata-section { border-left: 3px solid var(--accent); padding-left: 1rem; }
.incoming { color: var(--muted); font-size: 1.05rem; }
.incoming a { color: var(--link); }
.incoming > div { padding: .3rem 0; }
.notes {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 4px; padding: 1.25rem 1.5rem; margin: .75rem 0;
  font-size: 1.15rem;
}
.notes p { margin-bottom: .75rem; }
.notes p:last-child { margin-bottom: 0; }
.index-group { margin-bottom: 1.5rem; }
.index-item {
  padding: .5rem 0; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: baseline;
  gap: .5rem;
}
.index-item a { flex: 1; min-width: 0; }
.index-item .type-tag { font-size: .85rem; flex-shrink: 0; }
nav { margin-bottom: 2rem; font-size: 1.1rem; }
nav a { margin-right: 1rem; }
.breadcrumb { font-size: 1rem; color: var(--muted); margin-bottom: 1rem; }
.breadcrumb a { color: var(--muted); }
footer {
  margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: .9rem; color: var(--muted);
}
@media (max-width: 600px) {
  body { font-size: 1.1rem; padding: 1.25rem 1rem; line-height: 1.7; }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.2rem; }
  .quad-table td:first-child {
    width: auto; min-width: 5rem;
    font-size: .8rem;
  }
  .quad-table td { font-size: 1rem; padding: .35rem .3rem; }
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
.holon-meta { font-size: 1.1rem; color: var(--muted); margin: .25rem 0; }
.holon-member {
  border: 1px solid var(--border); border-radius: 4px;
  padding: 1.5rem 1.75rem; margin-bottom: 1.25rem;
  background: var(--card-bg);
}
.holon-member h3 { font-size: 1.35rem; margin-bottom: .35rem; }
.holon-member h3 a { color: var(--fg); }
.holon-member .member-meta {
  font-size: .95rem; color: var(--muted); margin-bottom: .5rem;
}
.holon-member .member-meta .type-tag { font-size: .85rem; }
.holon-member .member-notes { font-size: 1.15rem; line-height: 1.7; }
.holon-member .member-notes p { margin-bottom: .6rem; }
.holon-member .member-notes p:last-child { margin-bottom: 0; }
.expr-badge {
  display: inline-block; background: var(--accent); color: #fff;
  padding: .15rem .5rem; border-radius: 3px; font-size: .85rem;
  margin-left: .5rem; vertical-align: middle;
}
.whole-link {
  font-size: .95rem; color: var(--muted); margin-left: .5rem;
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


# ── Context Cloud ─────────────────────────────────────

CONTEXT_CLOUD_CSS = """\
:root {
  --bg: #fffff8;
  --fg: #111;
  --accent: #2d6a4f;
  --border: #d4d4d0;
  --muted: #6b6b68;
  --link: #2d6a4f;
  --tag-bg: #e8e8e4;
  --card-bg: #fafaf6;
  --body-width: 55%;
  --margin-width: 35%;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a18;
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
  font-family: et-book, Palatino, "Palatino Linotype",
               "Palatino LT STD", "Book Antiqua", Georgia, serif;
  font-size: 1.2rem;
  background: var(--bg); color: var(--fg);
  line-height: 1.8;
  padding: 0;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Article layout ── */
.article-container {
  display: flex;
  max-width: 1400px;
  margin: 0 auto;
  padding: 3rem 1.5rem;
  position: relative;
}
.article-body {
  width: var(--body-width);
  max-width: 38rem;
  padding-right: 4rem;
}
.article-margin {
  width: var(--margin-width);
  position: relative;
}

/* ── Typography ── */
.article-body h1 {
  font-size: 2.2rem;
  font-weight: 400;
  line-height: 1.2;
  margin-bottom: 0.5rem;
}
.article-body .subtitle {
  font-style: italic;
  font-size: 1.1rem;
  color: var(--muted);
  margin-bottom: 2.5rem;
  display: block;
}
.article-body h2 {
  font-size: 1.5rem;
  font-weight: 400;
  font-style: italic;
  color: var(--fg);
  margin: 2rem 0 0.75rem;
}
.article-body h3 {
  font-size: 1.2rem;
  font-weight: 400;
  font-style: italic;
  margin: 1.5rem 0 0.5rem;
}
.article-body p {
  margin-bottom: 1.2rem;
}
.article-body blockquote {
  border-left: 3px solid var(--border);
  padding-left: 1.5rem;
  margin: 1.5rem 0;
  color: var(--muted);
  font-size: 1.1rem;
}

/* ── Margin cards ── */
.margin-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  font-size: 0.85rem;
  line-height: 1.6;
  position: relative;
}
.margin-card .card-title {
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}
.margin-card .card-title a { color: var(--fg); }
.margin-card .card-type {
  display: inline-block;
  background: var(--tag-bg);
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  font-size: 0.75rem;
  font-family: "IBM Plex Mono", monospace;
  color: var(--muted);
  margin-bottom: 0.5rem;
}
.margin-card .card-body {
  color: var(--fg);
}
.margin-card .card-body p {
  margin-bottom: 0.5rem;
}
.margin-card .card-body p:last-child { margin-bottom: 0; }
.margin-card .card-note {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
  font-style: italic;
  color: var(--muted);
}
.margin-card .card-more {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--link);
}

/* ── Margin reference number ── */
.margin-ref {
  font-size: 0.75rem;
  color: var(--accent);
  vertical-align: super;
  line-height: 0;
  cursor: pointer;
  font-weight: 600;
}
.margin-card .ref-num {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  font-size: 0.75rem;
  color: var(--accent);
  font-weight: 600;
}

/* ── Footer ── */
.article-footer {
  max-width: 38rem;
  margin: 3rem auto;
  padding: 1.5rem 0;
  border-top: 1px solid var(--border);
  font-size: 0.9rem;
  color: var(--muted);
}
.article-footer .clone-info {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.85rem;
}

/* ── Narrow screen: collapse to footnotes ── */
@media (max-width: 960px) {
  .article-container {
    display: block;
    padding: 2rem 1rem;
  }
  .article-body {
    width: 100%;
    max-width: 100%;
    padding-right: 0;
  }
  .article-margin {
    display: none;
  }
  .margin-ref {
    cursor: pointer;
  }
  .footnote-section {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 2px solid var(--border);
  }
  .footnote-section h2 {
    font-size: 1.2rem;
    font-style: italic;
    font-weight: 400;
    margin-bottom: 1rem;
  }
  .footnote-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  .footnote-card .card-title {
    font-weight: 600;
    margin-bottom: 0.25rem;
  }
}
@media (min-width: 961px) {
  .footnote-section { display: none; }
}
"""


# ── Margin marker parser ─────────────────────────────

MARGIN_RE = re.compile(
    r"@@margin:"
    r"([A-Za-z0-9_-]+)"          # slug (required)
    r"(?::([^:@]*))?"            # label (optional)
    r"(?::([^@]*))?"             # note (optional)
    r"@@"
)


def _parse_margin_markers(text: str) -> list[dict]:
    """Extract @@margin:SLUG@@, @@margin:SLUG:LABEL@@,
    @@margin:SLUG:LABEL:NOTE@@ markers from article text.

    Returns list of {slug, label, note, position} dicts in order.
    """
    markers = []
    for m in MARGIN_RE.finditer(text):
        markers.append({
            "slug": m.group(1),
            "label": m.group(2) or "",
            "note": m.group(3) or "",
            "position": m.start(),
        })
    return markers


def _extract_article_body(filepath: str) -> str:
    """Extract the full body text of an article card.

    Returns everything after the property drawer and #+TITLE line,
    excluding ** sections that are Hoard structural (Relations,
    Membership, Expression, Order, Primary, References).
    """
    if not filepath or not os.path.exists(filepath):
        return ""
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    body_lines = []
    past_header = False
    skip_section = False
    structural_sections = {
        "Relations", "Membership", "Expression", "Order",
        "Primary", "References", "Scope Note",
    }

    for line in lines:
        # Skip property drawer
        if not past_header:
            if line.strip() == ":END:":
                past_header = True
            continue
        # Skip #+TITLE
        if line.startswith("#+TITLE:"):
            continue
        # Skip structural sections
        heading = re.match(r"^\*\*\s+(.+)", line)
        if heading:
            section_name = heading.group(1).strip()
            if section_name in structural_sections:
                skip_section = True
                continue
            else:
                skip_section = False
        if skip_section:
            continue
        body_lines.append(line)

    return "\n".join(body_lines).strip()


def _extract_scope_note(hord_root: str, uuid: str) -> str:
    """Extract scope note from a card's quads."""
    for q in read_all_quads(hord_root, uuid):
        if q.predicate == "v:sn":
            return q.object
    return ""


def _org_body_to_html(text: str) -> str:
    """Convert org-mode body text to HTML, handling basic markup.

    Handles: paragraphs, headings (*** → h3), bold, italic,
    code, links, blockquotes, and @@margin:...@@ markers.
    Margin markers are replaced with numbered superscript refs.
    """
    if not text:
        return ""

    # Split into blocks by blank lines
    blocks = re.split(r"\n\s*\n", text)
    html_parts = []
    ref_counter = [0]  # mutable for closure

    def _process_inline(line: str) -> str:
        """Process inline org markup."""
        # Escape HTML first
        line = escape(line)
        # Bold: *text*
        line = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", line)
        # Italic: /text/
        line = re.sub(r"(?<!\w)/([^/]+)/(?!\w)", r"<em>\1</em>", line)
        # Code: =text= or ~text~
        line = re.sub(r"[=~]([^=~]+)[=~]", r"<code>\1</code>", line)
        # Org links: [[url][label]]
        line = re.sub(
            r"\[\[([^\]]+)\]\[([^\]]+)\]\]",
            r'<a href="\1">\2</a>', line
        )
        # Margin markers → superscript refs
        def _replace_margin(m):
            ref_counter[0] += 1
            n = ref_counter[0]
            return f'<span class="margin-ref" id="ref-{n}">{n}</span>'
        line = MARGIN_RE.sub(_replace_margin, line)
        return line

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Heading (*** level → h3, **** → h4)
        heading = re.match(r"^(\*{3,4})\s+(.+)", block)
        if heading:
            level = len(heading.group(1))
            tag = f"h{level}"
            html_parts.append(f"<{tag}>{_process_inline(heading.group(2))}</{tag}>")
            continue

        # Blockquote (lines starting with >)
        if block.startswith(">") or block.startswith("    "):
            quote_lines = []
            for line in block.split("\n"):
                line = re.sub(r"^>\s?", "", line)
                line = re.sub(r"^    ", "", line)
                quote_lines.append(line)
            quote_text = _process_inline(" ".join(quote_lines))
            html_parts.append(f"<blockquote><p>{quote_text}</p></blockquote>")
            continue

        # Regular paragraph
        lines = block.split("\n")
        processed = " ".join(_process_inline(l.strip()) for l in lines if l.strip())
        html_parts.append(f"<p>{processed}</p>")

    return "\n".join(html_parts)


def _resolve_card_content(slug: str, hord_root: str, index: dict,
                          path_for_uuid: dict, expr_prefer: str = None,
                          label: str = "", note: str = "") -> dict:
    """Resolve a margin card's display content using the cascade:
    1. Inline note (from marker)
    2. Expression card text (if holon has expression preference)
    3. Scope note
    4. First paragraph of Notes section

    Returns dict with: uuid, title, type_label, body_html, note, has_more
    """
    uuid = index.get(slug)
    if not uuid:
        # Try partial match
        for key, val in index.items():
            if key.startswith(slug) and len(slug) >= 4:
                uuid = val
                slug = key
                break
    if not uuid:
        return {"uuid": "", "title": slug, "type_label": "?",
                "body_html": "<p><em>Card not found</em></p>",
                "note": note, "has_more": False}

    title = label or _resolve_title(uuid, hord_root)
    card_type = _get_card_type(hord_root, uuid) or ""

    # Load vocab for type label
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None
    type_label = vocab.label(card_type) if vocab and card_type else ""

    # Cascade: note → expression → scope note → first paragraph
    body_text = ""
    has_more = False

    # 1. Check for expression card
    if expr_prefer:
        expr_uuid = find_expression_for(hord_root, uuid, expr_prefer)
        if expr_uuid:
            source = path_for_uuid.get(expr_uuid)
            if source:
                body_text = _extract_notes(os.path.join(hord_root, source))
                has_more = True

    # 2. Scope note
    if not body_text:
        body_text = _extract_scope_note(hord_root, uuid)

    # 3. First paragraph of Notes
    if not body_text:
        source = path_for_uuid.get(uuid)
        if source:
            notes = _extract_notes(os.path.join(hord_root, source))
            if notes:
                # Take first paragraph only
                first_para = notes.split("\n\n")[0].strip()
                body_text = first_para
                if len(notes) > len(first_para):
                    has_more = True

    # Truncate at ~150 words
    words = body_text.split()
    if len(words) > 150:
        body_text = " ".join(words[:150]) + "…"
        has_more = True

    body_html = _text_to_html(body_text) if body_text else ""

    return {
        "uuid": uuid,
        "title": title,
        "type_label": type_label,
        "body_html": body_html,
        "note": note,
        "has_more": has_more,
    }


def render_context_cloud(holon_uuid: str, hord_root: str,
                         vocab: Vocabulary, path_for_uuid: dict,
                         standalone: bool = False) -> str:
    """Render a context-cloud holon as a Tufte-style article page.

    The primary card's body becomes the main article text.
    @@margin:SLUG@@ markers in the text place reference cards
    in the right margin at the corresponding vertical position.
    """
    holon_quads = read_all_quads(hord_root, holon_uuid)

    # Extract holon metadata
    holon_title = holon_uuid
    primary_uuid = None
    expr_prefer = None
    members = set()

    for q in holon_quads:
        if q.predicate == "v:title":
            holon_title = q.object
        elif q.predicate == "v:h-primary":
            primary_uuid = q.object
        elif q.predicate == "v:h-expr":
            expr_prefer = q.object
        elif q.predicate == "v:h-member":
            members.add(q.object)

    if not primary_uuid:
        return f"<p>Error: holon '{holon_title}' has no primary card.</p>"

    # Load index
    index = load_index(hord_root)

    # Get primary card source and extract article body
    primary_path = path_for_uuid.get(primary_uuid)
    if not primary_path:
        return f"<p>Error: primary card {primary_uuid} has no source file.</p>"

    full_primary_path = os.path.join(hord_root, primary_path)
    article_text = _extract_article_body(full_primary_path)
    primary_title = _resolve_title(primary_uuid, hord_root)

    # Parse margin markers from article text
    markers = _parse_margin_markers(article_text)

    # Resolve each margin card
    margin_cards = []
    for i, marker in enumerate(markers):
        card = _resolve_card_content(
            marker["slug"], hord_root, index, path_for_uuid,
            expr_prefer=expr_prefer,
            label=marker["label"],
            note=marker["note"],
        )
        card["ref_num"] = i + 1
        margin_cards.append(card)

    # Convert article body to HTML (replaces markers with superscripts)
    article_html = _org_body_to_html(article_text)

    # Extract holon description for subtitle
    holon_source = path_for_uuid.get(holon_uuid)
    holon_desc = ""
    if holon_source:
        holon_desc = _extract_holon_description(
            os.path.join(hord_root, holon_source))

    # ── Build page ──

    body_parts = []
    body_parts.append('<div class="article-container">')

    # ── Left column: article body ──
    body_parts.append('<div class="article-body">')
    body_parts.append(f"<h1>{escape(primary_title)}</h1>")
    if holon_desc:
        body_parts.append(f'<span class="subtitle">{escape(holon_desc)}</span>')
    body_parts.append(article_html)
    body_parts.append("</div>")  # .article-body

    # ── Right column: margin cards ──
    body_parts.append('<div class="article-margin">')
    for card in margin_cards:
        parts = []
        parts.append(f'<div class="margin-card" id="card-{card["ref_num"]}">')
        parts.append(f'<span class="ref-num">{card["ref_num"]}</span>')

        # Title
        if card["uuid"]:
            title_link = f'<a href="cards/{_entity_filename(card["uuid"])}">'
            title_link += f'{escape(card["title"])}</a>'
        else:
            title_link = escape(card["title"])
        parts.append(f'<div class="card-title">{title_link}</div>')

        # Type badge
        if card["type_label"]:
            parts.append(f'<span class="card-type">{escape(card["type_label"])}</span>')

        # Body
        if card["body_html"]:
            parts.append(f'<div class="card-body">{card["body_html"]}</div>')

        # Inline note
        if card["note"]:
            parts.append(f'<div class="card-note">{escape(card["note"])}</div>')

        # Read more
        if card["has_more"] and card["uuid"]:
            parts.append(
                f'<a class="card-more" '
                f'href="cards/{_entity_filename(card["uuid"])}">Read more →</a>'
            )

        parts.append("</div>")  # .margin-card
        body_parts.append("\n".join(parts))

    body_parts.append("</div>")  # .article-margin
    body_parts.append("</div>")  # .article-container

    # ── Footnote section (visible on narrow screens only) ──
    body_parts.append('<div class="footnote-section">')
    body_parts.append("<h2>References</h2>")
    for card in margin_cards:
        parts = []
        parts.append(f'<div class="footnote-card" id="fn-{card["ref_num"]}">')
        fn_title = f'<strong>{card["ref_num"]}.</strong> {escape(card["title"])}'
        if card["type_label"]:
            fn_title += f' <span class="card-type">{escape(card["type_label"])}</span>'
        parts.append(f'<div class="card-title">{fn_title}</div>')
        if card["body_html"]:
            parts.append(f'<div class="card-body">{card["body_html"]}</div>')
        if card["note"]:
            parts.append(f'<div class="card-note">{escape(card["note"])}</div>')
        parts.append("</div>")
        body_parts.append("\n".join(parts))
    body_parts.append("</div>")

    # ── Footer ──
    body_parts.append('<div class="article-footer">')
    body_parts.append(f'<p>Part of <em>{escape(holon_title)}</em>')
    body_parts.append(f' — {len(margin_cards)} reference cards</p>')
    body_parts.append('<div class="clone-info">')
    body_parts.append("Clone this article into your own hord:<br>")
    body_parts.append("<code>git clone [url] &amp;&amp; cd [dir] &amp;&amp; "
                      "hord compile</code>")
    body_parts.append("</div>")
    body_parts.append("</div>")

    page_content = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(primary_title)}</title>
<style>{CONTEXT_CLOUD_CSS}</style>
</head>
<body>
{page_content}
</body>
</html>
"""


# ── CLI command ────────────────────────────────────────

@click.command("export")
@click.option("--output", "-o", default="_site",
              help="Output directory (default: _site/)")
@click.option("--holon", "holon_name", default=None,
              help="Export a holon as a landing page with member cards")
@click.option("--context-cloud", "cloud_name", default=None,
              help="Export a holon as a Tufte-style context cloud article")
def export_cmd(output, holon_name, cloud_name):
    """Export the hord as a browsable HTML site.

    Generates one HTML page per entity plus an index page.
    All pages are self-contained with inline CSS — no
    external dependencies.

    With --holon, also generates a holon landing page that
    shows all members with expression substitution and
    inline notes.

    With --context-cloud, exports a holon as a Tufte-style
    standalone article with anchored margin cards.
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

    # Render context cloud if requested
    if cloud_name:
        cloud_uuid = index.get(cloud_name)
        if cloud_uuid is None:
            for key, val in index.items():
                if key.startswith(cloud_name) and len(cloud_name) >= 4:
                    cloud_uuid = val
                    break
        if cloud_uuid is None:
            click.echo(f"Warning: holon '{cloud_name}' not found, "
                       "skipping context cloud.", err=True)
        else:
            cloud_html = render_context_cloud(
                cloud_uuid, hord_root, vocab, path_for_uuid)
            # Write to article subdirectory
            cloud_title = _resolve_title(cloud_uuid, hord_root)
            cloud_slug = re.sub(r"[^a-z0-9]+", "-",
                                cloud_title.lower()).strip("-")
            cloud_dir = os.path.join(out_dir, cloud_slug)
            os.makedirs(cloud_dir, exist_ok=True)
            with open(os.path.join(cloud_dir, "index.html"), "w") as f:
                f.write(cloud_html)

            # Also render individual card pages in cards/ subdir
            cards_dir = os.path.join(cloud_dir, "cards")
            os.makedirs(cards_dir, exist_ok=True)
            for ent in entities:
                page = render_entity_page(
                    ent["uuid"], hord_root, vocab, index, path_for_uuid)
                if page:
                    with open(os.path.join(
                            cards_dir, _entity_filename(ent["uuid"])),
                            "w") as f:
                        f.write(page)

            click.echo(f"Context cloud: {cloud_dir}/index.html")

    click.echo(f"Exported {len(entities)} entities to {out_dir}/")
    click.echo(f"  Open {os.path.join(out_dir, 'index.html')} to browse.")
