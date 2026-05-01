"""hord web — local web interface for browsing and creating cards.

A lightweight read/write web UI for people who don't use Emacs.
Serves on localhost — not designed for public deployment.
"""

import json
import os
import re
import uuid as uuid_mod
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote_plus

import click

from hord.git_utils import find_hord_root, read_config
from hord.query import load_index, find_incoming, resolve_uuid_label
from hord.quad import read_all_quads, find_all_quads_dirs
from hord.vocab import Vocabulary, find_vocab
from hord.new import (TYPE_SHORTCUTS, TYPE_SUFFIX, TYPE_LABELS,
                      slugify, make_timestamp, scaffold_org, scaffold_md)
from hord.capture import capture_to_hord


# ── HTML templates ───────────────────────────────────────

_STYLE = """\
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
         background: #1a1a1a; color: #d4d4d4; line-height: 1.6;
         max-width: 900px; margin: 0 auto; padding: 1rem; }
  a { color: #7dba7d; text-decoration: none; }
  a:hover { text-decoration: underline; }
  h1 { font-size: 1.4rem; color: #8fa; margin-bottom: 0.5rem; }
  h2 { font-size: 1.1rem; color: #aaa; margin: 1.5rem 0 0.5rem; }
  .nav { margin-bottom: 1.5rem; padding-bottom: 0.5rem;
         border-bottom: 1px solid #333; }
  .nav a { margin-right: 1.5rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.4rem 0.75rem;
           border-bottom: 1px solid #2a2a2a; }
  th { color: #888; font-weight: normal; font-size: 0.85rem; }
  tr:hover { background: #222; }
  .type { color: #888; font-size: 0.85rem; }
  .uuid { color: #555; font-size: 0.75rem; font-family: monospace; }
  .section { margin: 1rem 0; padding: 0.75rem;
             background: #222; border-radius: 4px; }
  .section h3 { color: #8fa; font-size: 0.9rem; margin-bottom: 0.5rem; }
  .rel { margin: 0.25rem 0; }
  .rel-type { color: #888; display: inline-block; width: 4rem;
              text-align: right; margin-right: 0.5rem; }
  .body { white-space: pre-wrap; font-size: 0.95rem; }
  input, select, textarea { width: 100%; padding: 0.5rem;
    font-size: 1rem; background: #2a2a2a; color: #d4d4d4;
    border: 1px solid #444; border-radius: 4px; margin-top: 0.25rem; }
  textarea { height: 20vh; font-family: inherit; resize: vertical; }
  select { appearance: auto; }
  button { padding: 0.6rem 1.5rem; font-size: 1rem;
    background: #2d5a3d; color: #fff; border: none;
    border-radius: 4px; cursor: pointer; margin-top: 1rem; }
  button:hover { background: #3a7a50; }
  label { display: block; margin-top: 0.75rem; color: #aaa;
    font-size: 0.85rem; }
  .ok { color: #8fa; padding: 0.75rem; background: #1a2a1a;
    border-radius: 4px; margin: 1rem 0; }
  .count { color: #666; font-size: 0.85rem; }
"""

_NAV = '<div class="nav"><a href="/">Cards</a> <a href="/new">New Card</a> <a href="/capture">Capture</a></div>'


def _page(title, body):
    return f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — hord</title><style>{_STYLE}</style>
</head><body>{_NAV}{body}</body></html>"""


def _list_page(hord_root, index, vocab, query=""):
    """Render the card list page."""
    # Collect entities
    entities = []
    seen = set()
    for key, uid in index.items():
        if uid in seen or not _is_uuid(uid):
            continue
        seen.add(uid)
        title = resolve_uuid_label(hord_root, uid, vocab)
        quads = read_all_quads(hord_root, uid)
        etype = ""
        for q in quads:
            if q.predicate == "v:type":
                etype = q.object
                break
        entities.append((title, etype, uid))

    entities.sort(key=lambda e: e[0].lower())

    # Filter
    if query:
        q_lower = query.lower()
        entities = [e for e in entities if q_lower in e[0].lower()]

    rows = []
    for title, etype, uid in entities:
        type_label = vocab.label(f"v:type-{etype}") if vocab else etype
        if type_label.startswith("v:"):
            type_label = etype.replace("wh:", "")
        rows.append(
            f'<tr><td><a href="/card/{uid}">{_esc(title)}</a></td>'
            f'<td class="type">{_esc(type_label)}</td>'
            f'<td class="uuid">{uid[:8]}…</td></tr>')

    search_val = f' value="{_esc(query)}"' if query else ""
    html = f"""
    <h1>Cards <span class="count">({len(entities)})</span></h1>
    <form method="get" action="/" style="margin: 0.75rem 0;">
      <input name="q" placeholder="Filter by title…"{search_val}>
    </form>
    <table><tr><th>Title</th><th>Type</th><th>UUID</th></tr>
    {"".join(rows)}
    </table>"""
    return _page("Cards", html)


def _card_page(hord_root, uid, index, vocab):
    """Render a single card detail page."""
    quads = read_all_quads(hord_root, uid)
    if not quads:
        return _page("Not Found", "<p>Card not found.</p>")

    title = ""
    etype = ""
    relations = []
    meta = []

    for q in quads:
        if q.predicate == "v:title":
            title = q.object
        elif q.predicate == "v:type":
            etype = q.object
        elif q.predicate in ("v:tt", "v:pt", "v:bt", "v:btg", "v:bti",
                              "v:btp", "v:nt", "v:ntg", "v:nti", "v:ntp",
                              "v:rt", "v:uf", "v:use"):
            pred_label = vocab.label(q.predicate) if vocab else q.predicate
            if _is_uuid(q.object):
                obj_label = resolve_uuid_label(hord_root, q.object, vocab)
                relations.append((pred_label, obj_label, q.object))
            else:
                relations.append((pred_label, q.object, ""))
        else:
            pred_label = vocab.label(q.predicate) if vocab else q.predicate
            if _is_uuid(q.object):
                obj_label = resolve_uuid_label(hord_root, q.object, vocab)
                meta.append((pred_label, obj_label, q.object))
            else:
                meta.append((pred_label, q.object, ""))

    # Incoming
    incoming = find_incoming(hord_root, uid)
    inc_rels = []
    for q in incoming:
        pred_label = vocab.label(q.predicate) if vocab else q.predicate
        subj_label = resolve_uuid_label(hord_root, q.subject, vocab)
        inc_rels.append((pred_label, subj_label, q.subject))

    # Read body from source file
    body_text = _read_card_body(hord_root, uid, index)

    # Build HTML
    type_label = etype.replace("wh:", "") if etype else "unknown"
    parts = [f'<h1>{_esc(title)}</h1>',
             f'<div class="uuid">{uid} · {_esc(type_label)}</div>']

    if relations:
        rels_html = "".join(
            f'<div class="rel"><span class="rel-type">{_esc(p)}</span>'
            f'{_link(o, u)}</div>'
            for p, o, u in relations)
        parts.append(f'<div class="section"><h3>Relations</h3>{rels_html}</div>')

    if meta:
        meta_html = "".join(
            f'<div class="rel"><span class="rel-type">{_esc(p)}</span>'
            f'{_link(o, u)}</div>'
            for p, o, u in meta)
        parts.append(f'<div class="section"><h3>Metadata</h3>{meta_html}</div>')

    if body_text:
        parts.append(f'<div class="section"><h3>Notes</h3>'
                      f'<div class="body">{_esc(body_text)}</div></div>')

    if inc_rels:
        inc_html = "".join(
            f'<div class="rel"><span class="rel-type">← {_esc(p)}</span>'
            f'{_link(o, u)}</div>'
            for p, o, u in inc_rels)
        parts.append(f'<div class="section"><h3>Incoming</h3>{inc_html}</div>')

    return _page(title, "\n".join(parts))


def _new_card_page(message=""):
    """Render the new card form."""
    options = "".join(
        f'<option value="{short}">{short} — {label}</option>'
        for short, label in TYPE_LABELS)

    html = f"""
    <h1>New Card</h1>
    {message}
    <form method="post" action="/new">
      <label>Title</label>
      <input name="title" required autofocus>
      <label>Type</label>
      <select name="type">{options}</select>
      <label>Source (optional)</label>
      <input name="source" placeholder="e.g. reading, conversation">
      <label>Notes (optional)</label>
      <textarea name="notes"></textarea>
      <button type="submit">Create Card</button>
    </form>"""
    return _page("New Card", html)


def _capture_page(message=""):
    """Render the capture form."""
    html = f"""
    <h1>Quick Capture</h1>
    {message}
    <form method="post" action="/capture">
      <textarea name="content" placeholder="What's on your mind?"
                autofocus required></textarea>
      <label>Tags (space-separated)</label>
      <input name="tags" placeholder="e.g. idea hoard reading">
      <label>Source</label>
      <input name="source" value="web">
      <button type="submit">Capture</button>
    </form>"""
    return _page("Capture", html)


# ── Helpers ──────────────────────────────────────────────

def _esc(text):
    """HTML-escape text."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _link(label, uid):
    """Return HTML link to a card, or plain text if no UUID."""
    if uid:
        return f'<a href="/card/{uid}">{_esc(label)}</a>'
    return _esc(label)


def _is_uuid(s):
    return len(s) == 36 and s.count("-") == 4


def _read_card_body(hord_root, uid, index):
    """Read the Notes section body from a card's source file."""
    # Find filepath from index
    filepath = ""
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if os.path.exists(index_path):
        with open(index_path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[1] == uid:
                    candidate = os.path.join(hord_root, parts[0])
                    if os.path.exists(candidate):
                        filepath = candidate
                        break

    if not filepath:
        return ""

    try:
        with open(filepath) as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return ""

    # Extract Notes section (org)
    if filepath.endswith(".org"):
        m = re.search(r"^\*\* Notes\s*\n(.*?)(?=^\*\* |\Z)",
                       content, re.MULTILINE | re.DOTALL)
        if m:
            body = m.group(1).strip()
            # Strip property drawers from notes section
            body = re.sub(r"^\s*:PROPERTIES:.*?:END:\s*\n?", "",
                          body, flags=re.DOTALL)
            return body.strip()

    # Extract body (markdown)
    if filepath.endswith(".md"):
        if content.startswith("---"):
            end = content.find("\n---", 3)
            if end != -1:
                content = content[end + 4:]
        # Strip H1
        content = re.sub(r"^#\s+.*\n?", "", content, count=1)
        return content.strip()

    return ""


def _parse_form_body(body):
    """Parse form-urlencoded POST body."""
    result = {}
    for pair in body.split("&"):
        if "=" in pair:
            key, val = pair.split("=", 1)
            result[unquote_plus(key)] = unquote_plus(val)
    return result


# ── HTTP Handler ─────────────────────────────────────────

class WebHandler(BaseHTTPRequestHandler):
    hord_root = "."
    _index = None
    _vocab = None

    @classmethod
    def _load(cls):
        cls._index = load_index(cls.hord_root)
        vocab_path = find_vocab(cls.hord_root)
        cls._vocab = Vocabulary.load(vocab_path) if vocab_path else None

    def do_GET(self):
        if self._index is None:
            self.__class__._load()

        path = self.path.split("?")[0]
        query = ""
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for pair in qs.split("&"):
                if pair.startswith("q="):
                    query = unquote_plus(pair[2:])

        if path == "/" or path == "/cards":
            html = _list_page(self.hord_root, self._index, self._vocab, query)
        elif path.startswith("/card/"):
            uid = path[6:]
            html = _card_page(self.hord_root, uid, self._index, self._vocab)
        elif path == "/new":
            html = _new_card_page()
        elif path == "/capture":
            html = _capture_page()
        elif path == "/reload":
            self.__class__._load()
            html = _page("Reloaded", '<p class="ok">Hord data reloaded.</p>')
        else:
            html = _page("404", "<p>Not found.</p>")

        self._send_html(html)

    def do_POST(self):
        if self._index is None:
            self.__class__._load()

        path = self.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = _parse_form_body(body)

        if path == "/new":
            self._handle_new_card(data)
        elif path == "/capture":
            self._handle_capture(data)
        else:
            self._send_html(_page("404", "<p>Not found.</p>"))

    def _handle_new_card(self, data):
        title = data.get("title", "").strip()
        entity_type = data.get("type", "con").strip()
        source = data.get("source", "").strip()
        notes = data.get("notes", "").strip()

        if not title:
            self._send_html(_new_card_page(
                '<p style="color:#f88">Title is required.</p>'))
            return

        # Resolve type
        etype = entity_type.lower()
        if etype.startswith("wh:"):
            resolved = etype
        else:
            resolved = TYPE_SHORTCUTS.get(etype, "wh:con")

        config = read_config(self.hord_root)
        fmt = config.get("format", "org")

        card_uuid = str(uuid_mod.uuid4())
        timestamp = make_timestamp()
        suffix = TYPE_SUFFIX.get(resolved, "4")
        slug = slugify(title)
        ext = "org" if fmt == "org" else "md"
        filename = f"{slug}--{suffix}.{ext}"

        content_dir = "capture" if resolved == "wh:cap" else "content"
        out_dir = os.path.join(self.hord_root, content_dir)
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, filename)

        if os.path.exists(filepath):
            filename = f"{slug}_{card_uuid[:8]}--{suffix}.{ext}"
            filepath = os.path.join(out_dir, filename)

        if fmt == "org":
            content = scaffold_org(card_uuid, title, resolved, timestamp, source)
            # Insert notes if provided
            if notes:
                content = content.replace("** Notes\n\n\n",
                                          f"** Notes\n\n{notes}\n\n")
        else:
            content = scaffold_md(card_uuid, title, resolved, timestamp, source)
            if notes:
                content = content.rstrip() + f"\n{notes}\n"

        with open(filepath, "w") as f:
            f.write(content)

        # Reload index
        self.__class__._load()

        msg = (f'<div class="ok">Created: <a href="/card/{card_uuid}">'
               f'{_esc(title)}</a> ({card_uuid[:8]}…)</div>')
        self._send_html(_new_card_page(msg))

    def _handle_capture(self, data):
        text = data.get("content", "").strip()
        tags = data.get("tags", "").strip()
        source = data.get("source", "web").strip()

        if not text:
            self._send_html(_capture_page(
                '<p style="color:#f88">Nothing to capture.</p>'))
            return

        tag_list = [t.strip() for t in tags.split() if t.strip()]
        result = capture_to_hord(
            self.hord_root, text, tags=tag_list, source=source)

        # Reload
        self.__class__._load()

        msg = (f'<div class="ok">Captured: '
               f'<a href="/card/{result["uuid"]}">{result["uuid"][:8]}…</a>'
               f' ({", ".join(tag_list) if tag_list else "no tags"})</div>')
        self._send_html(_capture_page(msg))

    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging


# ── CLI ──────────────────────────────────────────────────

@click.command("web")
@click.option("--port", "-p", default=7750, help="Port (default: 7750)")
@click.option("--host", default="127.0.0.1", help="Host (default: localhost only)")
def web_cmd(port, host):
    """Start a local web interface for browsing and creating cards.

    Browse all cards, view details with relations and notes,
    create new cards, and quick-capture — all from a browser.
    No Emacs required.

    Examples:

        hord web                  # localhost:7750

        hord web -p 8080          # custom port

        hord web --host 0.0.0.0   # accessible on LAN
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    WebHandler.hord_root = hord_root

    server = HTTPServer((host, port), WebHandler)
    url = f"http://{host}:{port}/"
    click.echo(f"Hord web interface: {url}")
    click.echo(f"  Hord: {hord_root}")
    click.echo(f"  Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")
        server.server_close()
