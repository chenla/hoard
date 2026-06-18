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
  --bg: #fffff8;
  --fg: #111;
  --accent: #2d6a4f;
  --border: #d4d4d0;
  --muted: #6b6b68;
  --link: #2d6a4f;
  --tag-bg: #e8e8e4;
  --card-bg: #ffffff;
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
/* ── Reset ── */
* { margin: 0; padding: 0; box-sizing: border-box; }

/* ── Tufte-style base (matches context cloud) ── */
body {
  font-family: et-book, Palatino, "Palatino Linotype",
               "Palatino LT STD", "Book Antiqua", Georgia, serif;
  font-size: 1.4rem;
  line-height: 2rem;
  background: var(--bg); color: var(--fg);
  width: 87.5%;
  margin-left: auto; margin-right: auto;
  max-width: 1400px;
  padding: 3rem 0 3rem 8rem;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Typography — body text at 55% ── */
h1, h2, h3, p, blockquote, .scope-note, .quad-table,
.incoming, .incoming-inline, .notes, .references,
.strata-section, footer {
  width: 55%;
}
h1 {
  font-size: 2.2rem; font-weight: 400;
  margin-bottom: .35rem; line-height: 1.2;
}
h2 {
  font-size: 1.4rem; color: var(--accent);
  font-weight: 400; font-style: italic;
  margin: 2rem 0 .5rem;
}
h3 {
  font-size: 1.2rem; font-weight: 400;
  margin: 1.5rem 0 .5rem;
}
code { font-size: .9rem; word-break: break-all; }
.expr-callout {
  font-size: 1rem; color: var(--muted);
  font-style: italic; margin-bottom: 1.25rem;
  width: 55%;
}
.expr-callout a { color: var(--link); font-style: normal; }
.life-dates {
  font-size: 1.2rem; font-weight: 300;
  color: var(--muted);
}

.subtitle {
  font-family: "IBM Plex Mono", monospace;
  font-size: 1rem; color: var(--muted);
  margin-bottom: 1.5rem; width: 55%;
}
.type-tag {
  display: inline-block; background: var(--tag-bg);
  padding: .2rem .6rem; border-radius: 3px;
  font-size: .9rem; font-family: "IBM Plex Mono", monospace;
}

/* ── Quad table ── */
.quad-table { border-collapse: collapse; margin: .5rem 0; }
.quad-table td {
  padding: .45rem .6rem; border-bottom: 1px solid var(--border);
  font-size: 1.1rem; vertical-align: top;
}
.quad-table td:first-child {
  font-family: "IBM Plex Mono", monospace;
  font-size: .9rem; color: var(--muted);
  white-space: nowrap; width: 6rem; text-align: right;
  padding-right: 1rem; cursor: help;
}

/* ── Strata ── */
.strata-section { border-left: 3px solid var(--accent); padding-left: 1rem; }

/* ── Incoming links ── */
.incoming { color: var(--muted); font-size: 1.05rem; }
.incoming a { color: var(--link); }
.incoming > div { padding: .3rem 0; }
.incoming-inline {
  color: var(--muted); font-size: 1.05rem; line-height: 1.8;
}
.incoming-inline a { color: var(--link); }
.incoming-inline .sep { color: var(--border); margin: 0 .3rem; }

/* ── Notes ── */
.notes { margin: .75rem 0; font-size: 1.15rem; }
.notes p { margin-bottom: .75rem; width: 100%; }
.notes p:last-child { margin-bottom: 0; }
.notes h3 { width: 100%; }
.notes ul { width: 100%; margin: .5rem 0; padding-left: 1.5rem; }
.notes li { margin-bottom: .4rem; }

/* ── Index page ── */
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

/* ── References ── */
.references {
  font-size: 1.05rem; line-height: 1.65; color: var(--muted);
  margin: .75rem 0;
}
.references p { margin-bottom: .6rem; width: 100%; }
.references p:last-child { margin-bottom: 0; }
.references ul { list-style: none; padding: 0; width: 100%; }
.references li { margin-bottom: 1rem; }
.ref-annotation {
  display: block; margin-top: .25rem;
  font-size: .95rem; font-style: italic;
}

/* ── Scope note ── */
.scope-note {
  font-size: 1.15rem; line-height: 1.7; color: var(--fg);
  border-left: 3px solid var(--accent); padding-left: 1.25rem;
  margin: 1rem 0 1.75rem;
}
.scope-note p { margin: 0; width: 100%; }

/* ── Link group labels ── */
.link-group-label {
  font-size: 1.1rem; color: var(--muted); font-weight: 400;
  margin: 1.25rem 0 .25rem; font-style: italic;
  width: 55%;
}

/* ── Metadata sidebar — right margin ── */
.metadata-sidebar {
  float: right;
  clear: right;
  width: 35%;
  margin: 0 0 1rem 0;
  padding-right: 15%;
  padding-left: 2rem;
  font-size: 1.1rem;
  line-height: 1.4;
  color: var(--muted);
}
.metadata-sidebar .headshot {
  width: 100%;
  max-width: 220px;
  margin-bottom: .75rem;
  border-radius: 3px;
}
.metadata-sidebar dl { margin: 0; }
.metadata-sidebar dt {
  font-family: "IBM Plex Mono", monospace;
  font-size: .8rem;
  color: var(--accent);
  margin-top: .6rem;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.metadata-sidebar dt:first-child { margin-top: 0; }
.metadata-sidebar dd {
  margin: 0;
  font-size: 1rem;
  color: var(--fg);
}

/* ── Solvay photo strip (expression cards) ── */
.solvay-strip {
  float: right;
  clear: right;
  width: 220px;
  margin: 0 15% 1rem 2rem;
}
.solvay-strip img {
  display: none;
}
.solvay-strip .photo-crop {
  width: 100%;
  height: 280px;
  background-size: 1400px auto;
  background-repeat: no-repeat;
  border-radius: 3px;
}
.solvay-strip .strip-caption {
  font-size: 0.85rem;
  color: var(--muted);
  margin-top: 0.3rem;
  line-height: 1.4;
  font-style: italic;
}

/* ── Figures ── */
figure { margin: 2rem 0; }
figure.fullwidth { max-width: 100%; clear: both; }
figure.fullwidth img { width: 100%; }
figure figcaption {
  font-size: 0.9rem; color: var(--muted);
  margin-top: 0.5rem; line-height: 1.4;
  width: 55%;
}
figure.fullwidth figcaption { width: 100%; }

/* ── Navigation ── */
.breadcrumb {
  font-size: 1rem; color: var(--muted); margin-bottom: 1rem;
  width: 55%;
}
.breadcrumb a { color: var(--muted); }
footer {
  margin-top: 3rem; padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: .9rem; color: var(--muted);
}

/* ── Narrow screen ── */
@media (max-width: 960px) {
  body { width: 90%; padding: 1.5rem 0 1.5rem 1.5rem; font-size: 1.1rem; }
  h1, h2, h3, p, blockquote, .scope-note, .quad-table,
  .incoming, .incoming-inline, .notes, .references,
  .strata-section, .link-group-label, .subtitle,
  .breadcrumb, footer { width: 100%; }
  .metadata-sidebar {
    float: none; width: 100%; margin: 1rem 0;
    padding: 1rem; border: 1px solid var(--border);
    border-radius: 4px;
  }
  .solvay-strip {
    float: none; width: 100%; padding-left: 0; margin: 1rem 0;
  }
  .solvay-strip img { height: 120px; }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.2rem; }
  .quad-table td:first-child { width: auto; min-width: 4rem; font-size: .8rem; }
  .quad-table td { font-size: 1rem; padding: .35rem .3rem; }
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


def _extract_metadata(filepath: str) -> dict[str, str]:
    """Extract the Metadata property drawer from a card file.

    Returns a dict of property name → value, preserving order.
    """
    if not filepath or not os.path.exists(filepath):
        return {}
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    in_metadata = False
    in_props = False
    props = {}

    for line in lines:
        if re.match(r"^\*\*\s+Metadata\s*$", line):
            in_metadata = True
            continue
        if in_metadata and line.strip() == ":PROPERTIES:":
            in_props = True
            continue
        if in_props:
            if line.strip() == ":END:":
                break
            m = re.match(r"\s+:(\w+):\s*(.*)", line)
            if m:
                props[m.group(1)] = m.group(2).strip()
        elif in_metadata and re.match(r"^\*\*\s+", line):
            break

    return props


# Human-readable labels for metadata keys
_META_LABELS = {
    "BORN": "Born",
    "DIED": "Died",
    "NATIONALITY": "Nationality",
    "FIELD": "Field",
    "INSTITUTION": "Institution",
    "NOBEL": "Nobel Prize",
    "AGE_AT_SOLVAY": "Age at Solvay",
    "FOUNDED": "Founded",
    "LOCATION": "Location",
    "DATE": "Date",
    "THEME": "Theme",
    "ATTENDEES": "Attendees",
    "PRESIDENT": "President",
}


def _extract_org_section(content: str, heading: str) -> str:
    """Extract text between ** <heading> and the next ** heading or EOF."""
    lines = content.split("\n")
    in_section = False
    section_lines = []

    for line in lines:
        if re.match(rf"^\*\*\s+{re.escape(heading)}\s*$", line):
            in_section = True
            continue
        if in_section:
            if re.match(r"^\*\*\s+", line):
                break
            section_lines.append(line)

    return "\n".join(section_lines).strip()


def _extract_references(filepath: str) -> str:
    """Extract the References section body from an org file."""
    if not filepath or not os.path.exists(filepath):
        return ""
    with open(filepath, "r") as f:
        content = f.read()
    return _extract_org_section(content, "References")


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


def _html_page(title: str, body: str, nav: str = "",
               copyright_holder: str = "", copyright_year: str = "",
               license_text: str = "") -> str:
    """Wrap body content in a full HTML page."""
    footer_parts = ['Generated by <a href="https://github.com/chenla/hoard">Hoard</a>']
    if copyright_holder:
        footer_parts.append(
            f'&copy;{escape(copyright_year)} {escape(copyright_holder)}')
    if license_text:
        footer_parts.append(escape(license_text))
    footer_html = " &middot; ".join(footer_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{nav}
{body}
<footer>{footer_html}</footer>
</body>
</html>
"""


# ── Entity page ────────────────────────────────────────

def render_entity_page(uuid: str, hord_root: str, vocab: Vocabulary,
                       index: dict, path_for_uuid: dict,
                       index_href: str = "index.html",
                       hord_meta: dict = None) -> str:
    """Render a single entity as an HTML page."""
    quads = read_all_quads(hord_root, uuid)

    if not quads:
        return ""

    # Extract title, preferred term, type, and scope note
    raw_title = uuid
    preferred_term = ""
    entity_type = ""
    scope_note = ""
    for q in quads:
        if q.predicate == "v:title":
            raw_title = q.object
        elif q.predicate == "v:pt":
            preferred_term = q.object
        elif q.predicate == "v:type":
            entity_type = q.object
        elif q.predicate == "v:sn":
            scope_note = q.object

    # Display title: prefer PT (clean name) over v:title (has --N suffix)
    display_title = preferred_term or raw_title
    type_label = vocab.label(entity_type) if entity_type else ""

    # Separate structural and strata quads
    strata_preds = {"v:s-wo", "v:s-eo", "v:s-mo", "v:s-io", "v:s-type"}
    # Predicates to suppress from entity page display
    hidden_preds = {
        "v:title", "v:type", "v:sn", "v:tag", "v:pt",
        "v:h-member", "v:h-expr", "v:h-order", "v:h-cascade",
        "v:h-primary", "v:h-anchor",
    }
    structural = []
    strata = []

    for q in quads:
        if q.predicate in hidden_preds:
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
            # Add tooltip with scope note from vocabulary
            term = vocab.lookup(q.predicate)
            tooltip = f' title="{escape(term.scope_note)}"' if term and term.scope_note else ""
            if _looks_like_uuid(q.object):
                obj_title = _resolve_title(q.object, hord_root)
                obj_html = f'<a href="{_entity_filename(q.object)}">{escape(obj_title)}</a>'
            else:
                obj_html = escape(q.object)
            rows.append(f'<tr><td{tooltip}>{escape(pred_label)}</td><td>{obj_html}</td></tr>')
        return "\n".join(rows)

    # Check if this is an expression card
    is_expression = any(q.predicate in ("v:s-eo",) for q in quads)

    # Solvay photo crop positions for expression cards.
    # Maps slug prefix → (center_x_px, center_y_px) in the
    # original 3000x2171 image. The renderer scales the image
    # to 900px wide (ratio 0.3) and offsets so the person is
    # centered in the 220px container.
    _SOLVAY_PHOTO_POS = {
        # Front row (seated), y_center ~1400px
        # L→R: Langmuir, Planck, Curie, Lorentz, Einstein,
        #       Langevin, Guye, Wilson, Richardson
        "Irving_Langmuir":      (200, 1400),
        "Max_Planck":           (520, 1400),
        "Marie_Curie":          (920, 1400),
        "Hendrik_Lorentz":      (1100, 1400),
        "Albert_Einstein":      (1420, 1400),
        "Paul_Langevin":        (1700, 1400),
        "Charles-Eugene_Guye":  (1950, 1400),
        "CTR_Wilson":           (2250, 1400),
        "Owen_Richardson":      (2550, 1400),
        # Middle row, y_center ~1200px
        # L→R: Debye, Knudsen, Bragg, Kramers, Dirac,
        #       Compton, de Broglie, Born, Bohr
        "Peter_Debye":          (280, 1200),
        "Martin_Knudsen":       (550, 1200),
        "William_Lawrence_Bragg": (830, 1200),
        "Hendrik_Kramers":      (1100, 1200),
        "Paul_Dirac":           (1480, 1200),
        "Arthur_Compton":       (1620, 1200),
        "Louis_de_Broglie":     (1880, 1200),
        "Max_Born":             (2150, 1200),
        "Niels_Bohr":           (2450, 1200),
        # Back row, y_center ~650px
        # L→R: Piccard, Henriot, Ehrenfest, Herzen, de Donder,
        #       Schrödinger, Verschaffelt, Pauli, Heisenberg,
        #       Fowler, Brillouin
        "Auguste_Piccard":      (300, 650),
        "Emile_Henriot":        (530, 650),
        "Paul_Ehrenfest":       (780, 650),
        "Edouard_Herzen":       (1000, 650),
        "Theophile_de_Donder":  (1200, 650),
        "Erwin_Schrodinger":    (1430, 650),
        "Jules-Emile_Verschaffelt": (1650, 650),
        "Wolfgang_Pauli":       (1870, 650),
        "Werner_Heisenberg":    (2100, 650),
        "Ralph_Fowler":         (2350, 650),
        "Leon_Brillouin":       (2620, 650),
    }

    # Captions for each crop — simple identification
    _SOLVAY_PHOTO_CAPTION = {
        "Irving_Langmuir": "Irving Langmuir",
        "Max_Planck": "Max Planck",
        "Marie_Curie": "Marie Curie",
        "Hendrik_Lorentz": "Hendrik Lorentz",
        "Albert_Einstein": "Albert Einstein",
        "Paul_Langevin": "Paul Langevin",
        "Charles-Eugene_Guye": "Charles-Eugène Guye",
        "CTR_Wilson": "C.T.R. Wilson",
        "Owen_Richardson": "Owen Richardson",
        "Peter_Debye": "Peter Debye",
        "Martin_Knudsen": "Martin Knudsen",
        "William_Lawrence_Bragg": "William Lawrence Bragg",
        "Hendrik_Kramers": "Hendrik Kramers",
        "Paul_Dirac": "Paul Dirac",
        "Arthur_Compton": "Arthur Compton",
        "Louis_de_Broglie": "Louis de Broglie",
        "Max_Born": "Max Born",
        "Niels_Bohr": "Niels Bohr",
        "Auguste_Piccard": "Auguste Piccard",
        "Emile_Henriot": "Émile Henriot",
        "Paul_Ehrenfest": "Paul Ehrenfest",
        "Edouard_Herzen": "Édouard Herzen",
        "Theophile_de_Donder": "Théophile de Donder",
        "Erwin_Schrodinger": "Erwin Schrödinger",
        "Jules-Emile_Verschaffelt": "Jules-Émile Verschaffelt",
        "Wolfgang_Pauli": "Wolfgang Pauli",
        "Werner_Heisenberg": "Werner Heisenberg",
        "Ralph_Fowler": "Ralph Fowler",
        "Leon_Brillouin": "Léon Brillouin",
    }

    body_parts = []

    # Header — clean display title, type tag only (no UUID)
    # Append life dates for person Whole cards (not expressions)
    title_html = escape(display_title)
    source_path = path_for_uuid.get(uuid)
    metadata = {}
    if source_path:
        metadata = _extract_metadata(os.path.join(hord_root, source_path))
    if entity_type == "wh:per" and not is_expression and metadata:
        born = metadata.get("BORN", "")
        died = metadata.get("DIED", "")
        if born:
            birth_year = born.split("-")[0] if "-" in born else born.split(",")[0].strip()
            death_year = ""
            if died:
                death_year = died.split("-")[0] if "-" in died else died.split(",")[0].strip()
            if death_year:
                title_html += f' <span class="life-dates">({birth_year}–{death_year})</span>'
            else:
                title_html += f' <span class="life-dates">(b. {birth_year})</span>'
    body_parts.append(f"<h1>{title_html}</h1>")
    body_parts.append(f'<div class="subtitle">'
                      f'<span class="type-tag">{escape(type_label)}</span></div>')

    # Expression card callout — link to Whole card
    if is_expression:
        whole_uuid = None
        for q in quads:
            if q.predicate == "v:s-eo":
                whole_uuid = q.object
                break
        if whole_uuid:
            whole_title = _resolve_title(whole_uuid, hord_root)
            link_label = "Full record" if entity_type != "wh:per" else "Full biography"
            body_parts.append(
                f'<div class="expr-callout">'
                f'Temporal expression · '
                f'<a href="{_entity_filename(whole_uuid)}">'
                f'{link_label}: {escape(whole_title)} →</a></div>')

    # Metadata sidebar (float right, before scope note so text wraps)
    if source_path:
        if metadata:
            sidebar_parts = ['<aside class="metadata-sidebar">']
            # Headshot image (if present, render above the data)
            headshot = metadata.pop("HEADSHOT", None)
            if headshot:
                # Resolve path relative to page location
                media_prefix = "../" if "../" in index_href else ""
                sidebar_parts.append(
                    f'<img class="headshot" '
                    f'src="{media_prefix}{escape(headshot)}" '
                    f'alt="{escape(display_title)}">')
            sidebar_parts.append('<dl>')
            for key, value in metadata.items():
                label = _META_LABELS.get(key, key.replace("_", " ").title())
                sidebar_parts.append(
                    f'<dt>{escape(label)}</dt><dd>{escape(value)}</dd>')
            sidebar_parts.append('</dl></aside>')
            body_parts.append("\n".join(sidebar_parts))

    # Expression card: Solvay photo strip in right margin
    if is_expression and entity_type == "wh:per":
        # Find the slug from the source path to look up position
        if source_path:
            slug_base = os.path.basename(source_path).replace(
                "--solvay-1927.org", "")
            pos = _SOLVAY_PHOTO_POS.get(slug_base)
            if pos:
                media_prefix = "../" if "../" in index_href else ""
                photo_url = f'{media_prefix}lib/media/benjamin-couprie--1927-solvay-conference.jpg'
                # Scale factor: 1400px display / 3000px original
                scale = 1400.0 / 3000.0
                container_w, container_h = 220, 280
                # Person center in scaled coordinates
                sx = pos[0] * scale
                sy = pos[1] * scale
                # Offset so person is centered in container
                img_w = 1400
                img_h = int(2171 * scale)
                ox = max(0, min(sx - container_w / 2, img_w - container_w))
                oy = max(0, min(sy - container_h / 2, img_h - container_h))
                caption = _SOLVAY_PHOTO_CAPTION.get(
                    slug_base,
                    f'{display_title} at the Fifth Solvay Conference')
                body_parts.append(
                    f'<div class="solvay-strip">'
                    f'<div class="photo-crop" '
                    f'style="background-image: url(\'{photo_url}\'); '
                    f'background-position: -{ox:.0f}px -{oy:.0f}px;" '
                    f'role="img" '
                    f'aria-label="Solvay Conference 1927 — {escape(display_title)}">'
                    f'</div>'
                    f'<div class="strip-caption">'
                    f'{escape(caption)}, October 1927</div>'
                    f'</div>')

    # Scope note — lead paragraph (canonical definition)
    if scope_note:
        body_parts.append(f'<div class="scope-note"><p>{escape(scope_note)}</p></div>')

    # Structural relationships (skip PT since it's now the title)
    if structural:
        body_parts.append("<h2>Relationships</h2>")
        body_parts.append(f'<table class="quad-table">{quad_rows(structural)}</table>')

    # Strata (WEMI)
    if strata:
        body_parts.append('<h2>Strata (WEMI)</h2>')
        body_parts.append(f'<div class="strata-section"><table class="quad-table">{quad_rows(strata)}</table></div>')

    # Incoming links — grouped by relationship type
    incoming = find_incoming(hord_root, uuid)
    if incoming:
        body_parts.append("<h2>Connections</h2>")
        # Group incoming links by semantic category
        expr_links = []     # isExpressionOf → this card has expressions
        member_links = []   # MEMBER → this card belongs to holons
        rt_links = []       # RT → related cards
        bt_nt_links = []    # BT/NT → hierarchy
        other_links = []

        for q in incoming:
            pred = q.predicate
            if pred in ("v:s-eo", "strata:isExpressionOf"):
                expr_links.append(q)
            elif pred in ("v:h-member",):
                member_links.append(q)
            elif pred in ("v:rt",):
                rt_links.append(q)
            elif pred in ("v:bt", "v:nt"):
                bt_nt_links.append(q)
            else:
                other_links.append(q)

        def _render_link_group(label, qlist, inline=False):
            if not qlist:
                return
            body_parts.append(f'<h3 class="link-group-label">{escape(label)}</h3>')
            if inline:
                # Comma-separated flow for large groups
                body_parts.append('<div class="incoming-inline">')
                links = []
                for q in qlist:
                    subj_title = _resolve_title(q.subject, hord_root)
                    links.append(
                        f'<a href="{_entity_filename(q.subject)}">'
                        f'{escape(subj_title)}</a>')
                body_parts.append('<span class="sep"> · </span>'.join(links))
                body_parts.append("</div>")
            else:
                body_parts.append('<div class="incoming">')
                for q in qlist:
                    subj_title = _resolve_title(q.subject, hord_root)
                    body_parts.append(
                        f'<div><a href="{_entity_filename(q.subject)}">'
                        f'{escape(subj_title)}</a></div>'
                    )
                body_parts.append("</div>")

        _render_link_group("Expressions", expr_links)
        _render_link_group("Member of", member_links)
        # Sort related links alphabetically by title
        rt_links.sort(key=lambda q: _resolve_title(q.subject, hord_root).lower())
        _render_link_group("Related", rt_links, inline=True)
        _render_link_group("Hierarchy", bt_nt_links)
        _render_link_group("Other", other_links)

    # Notes (from source file)
    source_path = path_for_uuid.get(uuid)
    if source_path:
        full_path = os.path.join(hord_root, source_path)
        notes_text = _extract_notes(full_path)
        if notes_text:
            notes_html = _org_body_to_html(notes_text)
            # Fix media paths for subdirectory card pages
            if "../" in index_href:
                notes_html = notes_html.replace(
                    'src="lib/media/', 'src="../lib/media/')
            body_parts.append("<h2>Notes</h2>")
            body_parts.append(f'<div class="notes">{notes_html}</div>')

        # References section (bibliography / external sources)
        refs_text = _extract_references(full_path)
        if refs_text:
            refs_html = _org_body_to_html(refs_text)
            # Post-process: split annotations in <li> items.
            # Pattern: after the last period following a year or page
            # range, the remaining sentence is the annotation.
            def _split_ref_annotation(m):
                content = m.group(1)
                # Find last occurrence of year-period or pages-period
                # then wrap everything after it as annotation
                split = re.split(
                    r'(\d{4}\.|\d+–\d+\.|domain\.)',
                    content)
                if len(split) >= 3:
                    # Rejoin all but last part, last part is annotation
                    citation = "".join(split[:-1])
                    annotation = split[-1].strip()
                    if annotation:
                        return (f'<li>{citation}'
                                f'<span class="ref-annotation">'
                                f'{annotation}</span></li>')
                return m.group(0)
            refs_html = re.sub(
                r'<li>(.*?)</li>', _split_ref_annotation, refs_html)
            body_parts.append('<h2>References</h2>')
            body_parts.append(f'<div class="references">{refs_html}</div>')

    # Navigation bar
    prefix = "../" if "../" in index_href else ""
    nav = ('<nav class="breadcrumb">'
           f'<a href="{prefix}index-arc.html">Home</a>'
           f' · <a href="{prefix}index.html">Hord Index</a>'
           '</nav>')
    meta = hord_meta or {}
    return _html_page(display_title, "\n".join(body_parts), nav,
                      copyright_holder=meta.get("copyright_holder", ""),
                      copyright_year=meta.get("copyright_year", ""),
                      license_text=meta.get("license", ""))


def _resolve_title(uuid: str, hord_root: str) -> str:
    """Get the display title for a UUID from its quads.

    Prefers v:pt (preferred term / clean display name) over
    v:title (which may include filename suffixes like —7).
    """
    title = None
    for q in read_all_quads(hord_root, uuid):
        if q.predicate == "v:pt":
            return q.object
        if q.predicate == "v:title" and title is None:
            title = q.object
    return title or uuid[:8] + "…"


# ── Index page ─────────────────────────────────────────

def render_index_page(entities: list[dict], hord_name: str,
                      hord_meta: dict = None) -> str:
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

    meta = hord_meta or {}
    return _html_page(hord_name, "\n".join(body_parts),
                      copyright_holder=meta.get("copyright_holder", ""),
                      copyright_year=meta.get("copyright_year", ""),
                      license_text=meta.get("license", ""))


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
<footer>Generated by <a href="https://github.com/chenla/hoard">Hoard</a></footer>
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
    """Extract the description text from a holon card.

    Looks for free prose between structural sections — either
    between :END: and the first ** heading, or between
    ** Relations and ** Membership (where descriptions live
    in holons that have a Relations section).
    """
    if not filepath or not os.path.exists(filepath):
        return ""
    with open(filepath, "r") as f:
        content = f.read()
    lines = content.split("\n")

    # First try: text between :END: and first ** heading
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
    if desc_lines:
        return " ".join(desc_lines)

    # Second try: text between ** Relations and ** Membership
    # (skipping relation items that start with "- ")
    in_relations = False
    for line in lines:
        if re.match(r"^\*\*\s+Relations", line):
            in_relations = True
            continue
        if in_relations:
            if re.match(r"^\*\*\s+", line):
                break
            stripped = line.strip()
            if stripped and not stripped.startswith("- "):
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
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a18;
    --fg: #d4d4d0;
    --accent: #52b788;
    --border: #3a3a38;
    --muted: #9a9a96;
    --link: #52b788;
  }
}
/* ── Reset ── */
* { margin: 0; padding: 0; box-sizing: border-box; }

/* ── Base — matches tufte-css values ── */
body {
  font-family: et-book, Palatino, "Palatino Linotype",
               "Palatino LT STD", "Book Antiqua", Georgia, serif;
  font-size: 1.4rem;
  line-height: 2rem;
  background: var(--bg);
  color: var(--fg);
  width: 87.5%;
  margin-left: auto;
  margin-right: auto;
  max-width: 1400px;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Article ── */
article { padding: 5rem 0 5rem 8rem; }
section { padding-top: 1rem; padding-bottom: 1rem; }

/* ── Typography — body text at 55% ── */
p, blockquote, hr, h2, h3, .article-footer {
  width: 55%;
}
h1 {
  font-size: 2.4rem;
  font-weight: 400;
  line-height: 1.2;
  margin-top: 4rem;
  margin-bottom: 1.5rem;
  width: 55%;
}
.subtitle {
  font-style: italic;
  font-size: 1.1rem;
  color: var(--muted);
  margin-bottom: 2.5rem;
  display: block;
  width: 100%;
}
h2 {
  font-size: 1.5rem;
  font-weight: 400;
  font-style: italic;
  margin-top: 2.1rem;
  margin-bottom: 1.4rem;
}
p {
  margin-top: 1.4rem;
  margin-bottom: 1.4rem;
  padding-right: 0;
  vertical-align: baseline;
}
blockquote {
  border-left: 3px solid var(--border);
  padding-left: 1.5rem;
  margin: 1.5rem 0;
  color: var(--muted);
  font-size: 1.1rem;
}
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}

/* ── Sidenotes — tufte-css positioning ── */
.sidenote-ref {
  font-size: 0.75em;
  color: var(--accent);
  vertical-align: super;
  line-height: 0;
  font-weight: 600;
}
.sidenote {
  float: right;
  clear: right;
  margin-right: -60%;
  width: 50%;
  margin-top: 0.3rem;
  margin-bottom: 0;
  font-size: 1.1rem;
  line-height: 1.3;
  vertical-align: baseline;
  position: relative;
  color: var(--muted);
}
.sidenote .sn-num {
  font-size: 0.75em;
  color: var(--accent);
  font-weight: 600;
  margin-right: 0.1rem;
}
.sidenote .sn-title {
  font-weight: 600;
  font-size: 1rem;
}
.sidenote .sn-title a {
  color: var(--fg);
}
.sidenote .sn-title a:hover {
  color: var(--link);
}
.sidenote .sn-type {
  font-size: 0.8rem;
  color: var(--muted);
  font-style: italic;
  margin-left: 0.2rem;
}
.sidenote .sn-body {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.9rem;
}
.sidenote .sn-body p {
  width: 100%;
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.4;
}

/* ── Full-width figures (Tufte-style) ── */
figure {
  margin: 2rem 0;
}
figure.fullwidth {
  max-width: 100%;
  clear: both;
}
figure.fullwidth img {
  width: 100%;
}
figure figcaption {
  font-size: 0.9rem;
  color: var(--muted);
  margin-top: 0.5rem;
  line-height: 1.4;
  width: 55%;
}
figure.fullwidth figcaption {
  width: 100%;
}

/* ── Footer ── */
.article-footer {
  margin-top: 4rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
  font-size: 0.9rem;
  color: var(--muted);
}
.article-footer .clone-info {
  margin-top: 1rem;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.85rem;
}

/* ── Narrow screen: collapse to footnotes ── */
@media (max-width: 960px) {
  body { width: 90%; }
  p, blockquote, hr, h1, h2, h3,
  .subtitle, .article-footer { width: 100%; }
  .sidenote { display: none; }
  .sidenote-ref { cursor: pointer; }
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
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
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

FIGURE_RE = re.compile(
    r"@@figure:"
    r"([A-Za-z0-9_-]+)"          # media card slug (required)
    r"(?::([^@]*))?"             # caption override (optional)
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
    # Headings to strip (remove heading line but keep content below)
    strip_headings = {"Notes"}

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
            # Strip heading line but keep content
            if section_name in strip_headings:
                skip_section = False
                continue
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


def _resolve_figure(slug: str, hord_root: str, index: dict) -> dict:
    """Resolve a @@figure:SLUG@@ marker to image path and caption.

    Looks up the media card, reads v:media-file for the path and
    v:sn for the caption.  Returns {src, caption, title, uuid}.
    """
    uuid = index.get(slug)
    if not uuid:
        for key, val in index.items():
            if key.startswith(slug) and len(slug) >= 4:
                uuid = val
                break
    if not uuid:
        return {"src": "", "caption": slug, "title": slug, "uuid": ""}

    media_file = ""
    scope_note = ""
    title = slug
    for q in read_all_quads(hord_root, uuid):
        if q.predicate == "v:media-file":
            media_file = q.object
        elif q.predicate == "v:sn":
            scope_note = q.object
        elif q.predicate == "v:pt":
            title = q.object
        elif q.predicate == "v:title" and title == slug:
            title = q.object

    return {
        "src": media_file,
        "caption": scope_note or title,
        "title": title,
        "uuid": uuid,
    }


def _org_body_to_html(text: str, margin_cards: list[dict] = None,
                      hord_root: str = None, index: dict = None) -> str:
    """Convert org-mode body text to HTML, handling basic markup.

    Handles: paragraphs, headings (*** → h3), bold, italic,
    code, links, blockquotes, @@margin:...@@ and @@figure:...@@
    markers.

    If margin_cards is provided, margin markers are replaced with
    Tufte-style inline sidenotes. If hord_root and index are
    provided, figure markers are resolved to media card images.
    """
    if not text:
        return ""

    # Split into blocks by blank lines
    blocks = re.split(r"\n\s*\n", text)
    html_parts = []
    ref_counter = [0]  # mutable for closure

    def _build_sidenote(card: dict) -> str:
        """Build a Tufte-style sidenote span for a margin card."""
        n = card["ref_num"]
        parts = []
        parts.append(f'<span class="sidenote" id="sn-{n}">')
        parts.append(f'<span class="sn-num">{n}</span>')
        # Title as link to card page
        if card["uuid"]:
            parts.append(
                f'<span class="sn-title">'
                f'<a href="../cards/{_entity_filename(card["uuid"])}">'
                f'{escape(card["title"])}</a></span>')
        else:
            parts.append(f'<span class="sn-title">{escape(card["title"])}</span>')
        # Type label
        if card["type_label"]:
            parts.append(f'<span class="sn-type">{escape(card["type_label"])}</span>')
        # Body text (short) — strip <p> wrappers to keep inline
        if card["body_html"]:
            body = re.sub(r"</?p>", "", card["body_html"]).strip()
            if body:
                parts.append(f'<span class="sn-body"> — {body}</span>')
        parts.append("</span>")
        return "".join(parts)

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
        # Margin markers → superscript + inline sidenote
        def _replace_margin(m):
            ref_counter[0] += 1
            n = ref_counter[0]
            ref_html = f'<span class="sidenote-ref" id="ref-{n}">{n}</span>'
            if margin_cards and n <= len(margin_cards):
                ref_html += _build_sidenote(margin_cards[n - 1])
            return ref_html
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

        # Horizontal rule (--- or more dashes)
        if re.match(r"^-{3,}\s*$", block):
            html_parts.append("<hr>")
            continue

        # Figure marker: @@figure:SLUG@@ or @@figure:SLUG:caption@@
        fig_match = FIGURE_RE.search(block)
        if fig_match and hord_root and index:
            fig = _resolve_figure(fig_match.group(1), hord_root, index)
            caption_override = fig_match.group(2)
            caption = escape(caption_override) if caption_override else escape(fig["caption"])
            if fig["src"]:
                fig_parts = ['<figure class="fullwidth">']
                fig_src = f'../{fig["src"]}' if fig["src"].startswith("lib/") else fig["src"]
                fig_parts.append(f'<img src="{escape(fig_src)}" alt="{caption}">')
                if caption:
                    if fig["uuid"]:
                        card_link = f'../cards/{_entity_filename(fig["uuid"])}'
                        fig_parts.append(
                            f'<figcaption>{caption} '
                            f'<a href="{card_link}">→ image card</a>'
                            f'</figcaption>')
                    else:
                        fig_parts.append(f"<figcaption>{caption}</figcaption>")
                fig_parts.append("</figure>")
                html_parts.append("\n".join(fig_parts))
                continue

        # Image with optional caption: #+CAPTION: ...\n[[file:...]]
        img_match = re.search(
            r"\[\[file:([^\]]+)\]\]", block)
        if img_match:
            img_src = escape(img_match.group(1))
            caption_match = re.search(
                r"#\+CAPTION:\s*(.+)", block)
            caption = ""
            if caption_match:
                caption = _process_inline(caption_match.group(1).strip())
            fig_parts = ['<figure class="fullwidth">']
            fig_parts.append(f'<img src="{img_src}" alt="{escape(caption)}">')
            if caption:
                fig_parts.append(f"<figcaption>{caption}</figcaption>")
            fig_parts.append("</figure>")
            html_parts.append("\n".join(fig_parts))
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

        # Bullet list (lines starting with - )
        if re.match(r"^- ", block):
            # Reassemble continuation lines (indented under a - item)
            items = []
            current = ""
            for line in block.split("\n"):
                if re.match(r"^- ", line):
                    if current:
                        items.append(current.strip())
                    current = re.sub(r"^- ", "", line)
                elif line.strip():
                    current += " " + line.strip()
            if current:
                items.append(current.strip())
            li_parts = [f"<li>{_process_inline(item)}</li>" for item in items]
            html_parts.append(f'<ul>{"".join(li_parts)}</ul>')
            continue

        # Regular paragraph
        lines = block.split("\n")
        processed = " ".join(_process_inline(l.strip()) for l in lines if l.strip())
        html_parts.append(f"<p>{processed}</p>")

    return "\n".join(html_parts)


def _first_n_sentences(text: str, n: int = 2) -> str:
    """Extract the first N sentences from text."""
    # Split on sentence-ending punctuation followed by space
    parts = re.split(r'(?<=[.!?])\s+', text.strip(), maxsplit=n)
    return " ".join(parts[:n])


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

    # Cascade for margin display (short, leads reader to card):
    #   1. Scope note (canonical, brief)
    #   2. Expression card first sentence
    #   3. First sentence of Notes
    body_text = ""
    has_more = True  # always link to card for more

    # 1. Scope note (preferred — short canonical definition)
    body_text = _extract_scope_note(hord_root, uuid)

    # 2. Expression card (first two sentences)
    if not body_text and expr_prefer:
        expr_uuid = find_expression_for(hord_root, uuid, expr_prefer)
        if expr_uuid:
            source = path_for_uuid.get(expr_uuid)
            if source:
                notes = _extract_notes(os.path.join(hord_root, source))
                if notes:
                    body_text = _first_n_sentences(notes, 2)

    # 3. First two sentences of Notes
    if not body_text:
        source = path_for_uuid.get(uuid)
        if source:
            notes = _extract_notes(os.path.join(hord_root, source))
            if notes:
                body_text = _first_n_sentences(notes, 2)

    # Truncate at ~40 words for margin display
    words = body_text.split()
    if len(words) > 40:
        body_text = " ".join(words[:40]) + "…"

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
                         standalone: bool = False,
                         series_nav: str = "") -> str:
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

    # Convert article body to HTML with inline sidenotes
    article_html = _org_body_to_html(article_text, margin_cards,
                                     hord_root=hord_root, index=index)
    # Fix media paths — article is in a subdirectory of _site/
    article_html = article_html.replace('src="lib/media/', 'src="../lib/media/')

    # Extract holon description for subtitle
    holon_source = path_for_uuid.get(holon_uuid)
    holon_desc = ""
    if holon_source:
        holon_desc = _extract_holon_description(
            os.path.join(hord_root, holon_source))

    # ── Build page ──

    body_parts = []
    body_parts.append("<article>")
    body_parts.append("<section>")
    body_parts.append(f"<h1>{escape(primary_title)}</h1>")
    if holon_desc:
        body_parts.append(f'<span class="subtitle">{escape(holon_desc)}</span>')
    body_parts.append(article_html)
    body_parts.append("</section>")
    body_parts.append("</article>")

    # ── Footnote section (visible on narrow screens only) ──
    body_parts.append('<div class="footnote-section">')
    body_parts.append("<h2>References</h2>")
    for card in margin_cards:
        parts = []
        parts.append(f'<div class="footnote-card" id="fn-{card["ref_num"]}">')
        fn_title = f'<strong>{card["ref_num"]}.</strong> {escape(card["title"])}'
        if card["type_label"]:
            fn_title += f' <span class="sn-type">{escape(card["type_label"])}</span>'
        parts.append(f'<div class="card-title">{fn_title}</div>')
        if card["body_html"]:
            parts.append(f'<div class="card-body">{card["body_html"]}</div>')
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

    series_css = ""
    if series_nav:
        series_css = """
.series-nav {
  padding: 0 0 0 8rem;
  font-size: 1rem;
  color: var(--muted);
  margin-bottom: 0;
  width: 55%;
}
.series-nav a { color: var(--link); }
.series-nav .sep { margin: 0 0.5rem; }
.series-bottom {
  padding: 1.5rem 0 0 8rem;
  font-size: 1rem;
  color: var(--muted);
  width: 55%;
  border-top: 1px solid var(--border);
  margin-top: 2rem;
}
.series-bottom a { color: var(--link); }
.series-bottom .sep { margin: 0 0.5rem; }
@media (max-width: 960px) {
  .series-nav, .series-bottom { padding-left: 0; width: 100%; }
}
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(primary_title)}</title>
<style>{CONTEXT_CLOUD_CSS}{series_css}</style>
</head>
<body>
{series_nav}
{page_content}
{series_nav.replace('series-nav', 'series-bottom') if series_nav else ''}
</body>
</html>
"""


# ── Series landing page ───────────────────────────────

LANDING_CSS = """\
:root {
  --bg: #fffff8; --fg: #111; --accent: #2d6a4f;
  --border: #d4d4d0; --muted: #6b6b68; --link: #2d6a4f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a18; --fg: #d4d4d0; --accent: #52b788;
    --border: #3a3a38; --muted: #9a9a96; --link: #52b788;
  }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: et-book, Palatino, "Palatino Linotype",
               "Palatino LT STD", "Book Antiqua", Georgia, serif;
  font-size: 1.4rem; line-height: 2rem;
  background: var(--bg); color: var(--fg);
  width: 87.5%; margin-left: auto; margin-right: auto;
  max-width: 1400px; padding: 5rem 0 5rem 8rem;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 2.6rem; font-weight: 400; line-height: 1.2;
     margin-bottom: 0.5rem; width: 55%; }
.series-label { font-style: italic; font-size: 1.1rem;
  color: var(--muted); margin-bottom: 2.5rem; width: 55%; }
.intro { width: 55%; font-size: 1.25rem; line-height: 1.8;
         margin-bottom: 3rem; }
.intro p { margin-bottom: 1.4rem; }
.articles { width: 55%; margin-bottom: 3rem; }
.article-link { display: block; padding: 1.5rem 0;
                border-bottom: 1px solid var(--border); }
.article-link:first-child { border-top: 1px solid var(--border); }
.article-link:hover { text-decoration: none; }
.article-link:hover .article-title { text-decoration: underline; }
.article-num { font-size: 0.9rem; color: var(--accent);
  font-family: "IBM Plex Mono", monospace;
  text-transform: uppercase; letter-spacing: 0.1em; }
.article-title { font-size: 1.5rem; font-weight: 400;
  display: block; margin: 0.25rem 0; color: var(--fg); }
.article-desc { font-size: 1.05rem; color: var(--muted);
                line-height: 1.5; }
.meta-links { width: 55%; margin-top: 2rem;
              font-size: 1.05rem; color: var(--muted); }
.meta-links a { color: var(--link); }
.photo-float { float: right; width: 35%;
               margin: 0 7% 1.5rem 2rem; }
.photo-float img { width: 100%; border-radius: 2px; }
.photo-float .caption { font-size: 0.85rem; color: var(--muted);
                        margin-top: 0.4rem; line-height: 1.4; }
footer { margin-top: 4rem; padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.9rem; color: var(--muted); width: 55%; }
footer a { color: var(--link); }
@media (max-width: 960px) {
  body { width: 90%; padding: 2rem 0 2rem 1.5rem; }
  h1, .series-label, .intro, .articles,
  .meta-links, footer { width: 100%; }
  .photo-float { float: none; width: 100%; margin: 1rem 0; }
}
"""


def render_series_landing(cloud_info: list[dict], hord_root: str,
                          hord_meta: dict, num_entities: int,
                          num_holons: int) -> str:
    """Render a landing page for a multi-article series."""
    meta = hord_meta or {}

    # Find the Solvay photo for the sidebar (if it exists)
    photo_html = ""
    photo_path = os.path.join(hord_root, "lib", "media",
                              "benjamin-couprie--1927-solvay-conference.jpg")
    if os.path.exists(photo_path):
        photo_html = (
            '<div class="photo-float">\n'
            '  <img src="lib/media/benjamin-couprie--1927-solvay-conference.jpg"\n'
            '       alt="The 1927 Solvay Conference photograph">\n'
            '  <div class="caption">Brussels, October 1927. Twenty-nine physicists.\n'
            '    Seventeen Nobel laureates. The most intelligent photograph '
            'ever taken.</div>\n'
            '</div>\n')

    # Build article links
    articles_html = []
    for i, info in enumerate(cloud_info):
        desc = info.get("desc", "")
        articles_html.append(
            f'<a class="article-link" href="{info["slug"]}/index.html">\n'
            f'  <span class="article-num">Part {i + 1}</span>\n'
            f'  <span class="article-title">{escape(info["title"])}</span>\n'
            f'  <span class="article-desc">{escape(desc)}</span>\n'
            f'</a>\n')

    # Footer
    footer_parts = ['Generated by <a href="https://github.com/chenla/hoard">Hoard</a>']
    if meta.get("copyright_holder"):
        footer_parts.append(
            f'&copy;{escape(meta.get("copyright_year", ""))} '
            f'{escape(meta["copyright_holder"])}')
    if meta.get("license"):
        footer_parts.append(escape(meta["license"]))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Solvay Shockwave &mdash; Screed</title>
<style>{LANDING_CSS}</style>
</head>
<body>

{photo_html}
<h1>The Solvay Shockwave</h1>
<div class="series-label">Screed &middot; Tranche 1</div>

<div class="intro">
<p>In October 1927, twenty-nine physicists gathered in Brussels
for the Fifth Solvay Conference. The debates that erupted that
week &mdash; between Einstein and Bohr, between determinism and
probability, between the old physics and the new &mdash; shattered
the most foundational assumption of the modern West: that the
universe is a clockwork mechanism, fully knowable, fully
controllable.</p>

<p>The shockwave from that week propagated outward through
mathematics, through computation, through nuclear weapons,
through artificial intelligence. It is still propagating now.</p>

<p>These three articles trace that shockwave from the photograph
to the present. Each is a self-contained piece; together they
tell one story.</p>
</div>

<div class="articles">
{"".join(articles_html)}
</div>

<div class="meta-links">
  <a href="index.html">Hord Index</a> &middot;
  {num_entities} cards &middot; {num_holons} holons &middot;
  <a href="https://chenla.substack.com">Screed on Substack</a>
</div>

<footer>
  {" &middot; ".join(footer_parts)}
</footer>

</body>
</html>
"""


# ── CLI command ────────────────────────────────────────

@click.command("export")
@click.option("--output", "-o", default="_site",
              help="Output directory (default: _site/)")
@click.option("--holon", "holon_name", default=None,
              help="Export a holon as a landing page with member cards")
@click.option("--context-cloud", "cloud_names", multiple=True,
              help="Export holon(s) as context cloud articles (repeatable)")
def export_cmd(output, holon_name, cloud_names):
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

    # Read hord config
    hord_name = "Hord"
    hord_meta = {"copyright_holder": "", "copyright_year": "", "license": ""}
    config_path = os.path.join(hord_root, ".hord", "config.toml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("name"):
                    match = re.search(r'"(.+)"', line)
                    if match:
                        hord_name = match.group(1)
                for key in hord_meta:
                    if line.startswith(key):
                        match = re.search(r'"(.+)"', line)
                        if match:
                            hord_meta[key] = match.group(1)

    # Render index
    index_html = render_index_page(entities, hord_name, hord_meta=hord_meta)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(index_html)

    # Render entity pages
    for ent in entities:
        page = render_entity_page(ent["uuid"], hord_root, vocab, index, path_for_uuid,
                                  hord_meta=hord_meta)
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

    # Render context clouds if requested
    if cloud_names:
        import shutil

        # Shared card pages — render once for all clouds
        cards_dir = os.path.join(out_dir, "cards")
        os.makedirs(cards_dir, exist_ok=True)
        for ent in entities:
            page = render_entity_page(
                ent["uuid"], hord_root, vocab, index, path_for_uuid,
                index_href="../index.html",
                hord_meta=hord_meta)
            if page:
                with open(os.path.join(
                        cards_dir, _entity_filename(ent["uuid"])),
                        "w") as f:
                    f.write(page)

        # Shared media — copy once
        media_src = os.path.join(hord_root, "lib", "media")
        if os.path.isdir(media_src):
            media_dst = os.path.join(out_dir, "lib", "media")
            if os.path.exists(media_dst):
                shutil.rmtree(media_dst)
            os.makedirs(os.path.dirname(media_dst), exist_ok=True)
            shutil.copytree(media_src, media_dst)

        # Resolve all cloud UUIDs, titles, and slugs first (for series nav)
        cloud_info = []
        for cloud_name in cloud_names:
            cloud_uuid = index.get(cloud_name)
            if cloud_uuid is None:
                for key, val in index.items():
                    if key.startswith(cloud_name) and len(cloud_name) >= 4:
                        cloud_uuid = val
                        break
            if cloud_uuid is None:
                click.echo(f"Warning: holon '{cloud_name}' not found, "
                           "skipping context cloud.", err=True)
                continue
            cloud_title = _resolve_title(cloud_uuid, hord_root)
            cloud_slug = re.sub(r"[^a-z0-9]+", "-",
                                cloud_title.lower()).strip("-")
            # Extract holon description for landing page
            holon_source = path_for_uuid.get(cloud_uuid)
            cloud_desc = ""
            if holon_source:
                cloud_desc = _extract_holon_description(
                    os.path.join(hord_root, holon_source))
            cloud_info.append({
                "uuid": cloud_uuid, "title": cloud_title,
                "slug": cloud_slug, "desc": cloud_desc,
            })

        # Build series nav for each article (if multiple clouds)
        is_series = len(cloud_info) > 1
        for i, info in enumerate(cloud_info):
            nav_html = ""
            if is_series:
                parts = [f'<div class="series-nav">']
                parts.append(f'<a href="../index-arc.html">Series</a>')
                parts.append(f'<span class="sep">&middot;</span>')
                if i > 0:
                    prev = cloud_info[i - 1]
                    parts.append(
                        f'<a href="../{prev["slug"]}/index.html">'
                        f'&larr; {escape(prev["title"])}</a>')
                    parts.append(f'<span class="sep">&middot;</span>')
                parts.append(
                    f'Part {i + 1} of {len(cloud_info)}')
                if i < len(cloud_info) - 1:
                    nxt = cloud_info[i + 1]
                    parts.append(f'<span class="sep">&middot;</span>')
                    parts.append(
                        f'<a href="../{nxt["slug"]}/index.html">'
                        f'{escape(nxt["title"])} &rarr;</a>')
                parts.append("</div>")
                nav_html = "\n".join(parts)

            cloud_html = render_context_cloud(
                info["uuid"], hord_root, vocab, path_for_uuid,
                series_nav=nav_html)
            cloud_dir = os.path.join(out_dir, info["slug"])
            os.makedirs(cloud_dir, exist_ok=True)
            with open(os.path.join(cloud_dir, "index.html"), "w") as f:
                f.write(cloud_html)

            click.echo(f"Context cloud: {cloud_dir}/index.html")

        # Generate series landing page if multiple clouds
        if is_series:
            num_holons = sum(1 for e in entities if e.get("type") == "wh:holon")
            landing_html = render_series_landing(
                cloud_info, hord_root, hord_meta,
                num_entities=len(entities), num_holons=num_holons)
            landing_path = os.path.join(out_dir, "index-arc.html")
            with open(landing_path, "w") as f:
                f.write(landing_html)
            click.echo(f"Series landing: {landing_path}")

    click.echo(f"Exported {len(entities)} entities to {out_dir}/")
    click.echo(f"  Open {os.path.join(out_dir, 'index.html')} to browse.")
