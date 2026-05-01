"""hord mobile — mobile capture server and GitHub inbox processor.

Two complementary capture paths for mobile use:

1. HTTP server (fast path) — POST to /capture when laptop is live
2. GitHub inbox (durable path) — push to a GitHub repo, pull on cron

Both feed into the same pipeline: hord capture or scratch file.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import click

from hord.git_utils import find_hord_root, read_config
from hord.capture import capture_to_hord


# ── HTTP capture server ──────────────────────────────────

# Template for the capture form served at GET /
_FORM_HTML = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>hord capture</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, system-ui, sans-serif;
         background: #1a1a1a; color: #e0e0e0;
         padding: 1rem; max-width: 600px; margin: 0 auto; }}
  h1 {{ font-size: 1.2rem; margin-bottom: 1rem; color: #8fa; }}
  textarea {{ width: 100%; height: 40vh; padding: 0.75rem;
             font-size: 1rem; background: #2a2a2a; color: #e0e0e0;
             border: 1px solid #444; border-radius: 4px;
             font-family: inherit; resize: vertical; }}
  input {{ width: 100%; padding: 0.6rem; font-size: 1rem;
          background: #2a2a2a; color: #e0e0e0;
          border: 1px solid #444; border-radius: 4px;
          margin-top: 0.5rem; }}
  button {{ width: 100%; padding: 0.75rem; font-size: 1.1rem;
           background: #2d5a3d; color: #fff; border: none;
           border-radius: 4px; margin-top: 0.75rem; cursor: pointer; }}
  button:active {{ background: #3a7a50; }}
  .ok {{ color: #8fa; margin-top: 1rem; }}
  .err {{ color: #f88; margin-top: 1rem; }}
  label {{ font-size: 0.85rem; color: #aaa; display: block;
          margin-top: 0.75rem; }}
</style>
</head><body>
<h1>hord capture</h1>
<form method="POST" action="/capture">
  <textarea name="content" placeholder="What's on your mind?"
            autofocus></textarea>
  <label>Tags (space-separated)</label>
  <input name="tags" placeholder="e.g. hoard idea reading">
  <label>Source</label>
  <input name="source" placeholder="e.g. mobile, conversation, reading"
         value="mobile">
  <button type="submit">Capture</button>
</form>
{message}
</body></html>
"""


class CaptureHandler(BaseHTTPRequestHandler):
    """HTTP handler for mobile capture."""

    hord_root = "."
    auth_token = None
    scratch_mode = False

    def do_GET(self):
        if self.path == "/" or self.path == "/capture":
            self._serve_form("")
        elif self.path == "/health":
            self._json_response(200, {"status": "ok"})
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/capture":
            self._json_response(404, {"error": "not found"})
            return

        # Auth check
        if self.auth_token:
            auth = self.headers.get("Authorization", "")
            # Support both Bearer token and form-based (no auth header)
            if auth and not self._check_auth(auth):
                self._json_response(401, {"error": "unauthorized"})
                return

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        if "application/json" in content_type:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "invalid JSON"})
                return
            text = data.get("content", "").strip()
            tags = data.get("tags", "")
            source = data.get("source", "mobile")
            title = data.get("title")
        elif "x-www-form-urlencoded" in content_type:
            data = _parse_form(body)
            text = data.get("content", "").strip()
            tags = data.get("tags", "")
            source = data.get("source", "mobile")
            title = None
        else:
            # Treat raw body as plain text capture
            text = body.strip()
            tags = ""
            source = "mobile"
            title = None

        if not text:
            if "json" in content_type:
                self._json_response(400, {"error": "empty content"})
            else:
                self._serve_form('<p class="err">Nothing to capture.</p>')
            return

        tag_list = [t.strip() for t in tags.split() if t.strip()]

        if self.scratch_mode:
            result = _append_to_scratch(self.hord_root, text, tag_list, source)
        else:
            result = capture_to_hord(
                self.hord_root, text,
                tags=tag_list,
                source=source,
                title=title,
            )

        if "json" in content_type:
            self._json_response(200, result)
        else:
            self._serve_form(f'<p class="ok">Captured. {result.get("uuid", result.get("file", ""))}</p>')

    def _check_auth(self, auth_header: str) -> bool:
        """Verify Bearer token."""
        if auth_header.startswith("Bearer "):
            return hmac.compare_digest(auth_header[7:], self.auth_token)
        return False

    def _serve_form(self, message: str):
        html = _FORM_HTML.format(message=message)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _json_response(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        """Prefix log messages with timestamp."""
        click.echo(f"  [{time.strftime('%H:%M:%S')}] {args[0]}")


def _parse_form(body: str) -> dict:
    """Parse application/x-www-form-urlencoded body."""
    from urllib.parse import unquote_plus
    result = {}
    for pair in body.split("&"):
        if "=" in pair:
            key, val = pair.split("=", 1)
            result[unquote_plus(key)] = unquote_plus(val)
    return result


def _append_to_scratch(hord_root: str, text: str,
                       tags: list, source: str) -> dict:
    """Append capture to today's scratch file instead of creating a card."""
    config = read_config(hord_root)
    scratch_dir = os.path.expanduser(
        config.get("scratch_dir", "~/proj/ybr/bench/scratch/"))
    os.makedirs(scratch_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(scratch_dir, f"{today}.org")

    tag_str = f"  :{':'.join(tags)}:" if tags else ""
    entry = f"\n** Mobile capture [{datetime.now().strftime('%Y-%m-%d %a %H:%M')}]{tag_str}\n\n{text}\n"

    if not os.path.exists(filepath):
        header = datetime.now().strftime("#+TITLE: Scratch — %A %e %B %Y\n\n")
        with open(filepath, "w") as f:
            f.write(header)

    with open(filepath, "a") as f:
        f.write(entry)

    return {"file": os.path.basename(filepath), "status": "appended"}


# ── GitHub inbox processor ───────────────────────────────

def process_github_inbox(hord_root: str, inbox_dir: str,
                         archive: bool = True,
                         verbose: bool = False) -> int:
    """Process captured files from a GitHub inbox directory.

    Reads .md and .txt files from inbox_dir, runs each through
    hord capture, then either deletes or moves them to an
    archive/ subdirectory.

    Returns number of files processed.
    """
    if not os.path.isdir(inbox_dir):
        return 0

    processed = 0
    archive_dir = os.path.join(inbox_dir, "archive") if archive else None

    for fname in sorted(os.listdir(inbox_dir)):
        if fname.startswith(".") or fname == "archive" or fname == "README.md":
            continue
        if not fname.endswith((".md", ".txt", ".org")):
            continue

        fpath = os.path.join(inbox_dir, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            with open(fpath) as f:
                raw = f.read().strip()
        except (OSError, UnicodeDecodeError):
            continue

        if not raw:
            continue

        # Parse simple frontmatter if present
        tags = []
        source = "mobile"
        title = None
        content = raw

        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end != -1:
                fm = raw[4:end]
                content = raw[end + 4:].strip()
                for line in fm.split("\n"):
                    line = line.strip()
                    if line.startswith("tags:"):
                        tags = [t.strip() for t in line[5:].split()
                                if t.strip()]
                    elif line.startswith("source:"):
                        source = line[7:].strip()
                    elif line.startswith("title:"):
                        title = line[6:].strip()

        if not content:
            continue

        result = capture_to_hord(
            hord_root, content,
            tags=tags,
            source=source,
            title=title,
        )

        if verbose:
            click.echo(f"  {fname} → {result['uuid'][:8]}… "
                        f"({', '.join(tags) if tags else 'no tags'})")

        # Archive or delete
        if archive and archive_dir:
            os.makedirs(archive_dir, exist_ok=True)
            os.rename(fpath, os.path.join(archive_dir, fname))
        else:
            os.remove(fpath)

        processed += 1

    return processed


# ── CLI commands ─────────────────────────────────────────

@click.group("mobile")
def mobile_cmd():
    """Mobile capture: HTTP server and GitHub inbox processor.

    Two paths for capturing from your phone:

    1. HTTP server (fast path, requires laptop to be running):

        hord mobile serve

    2. GitHub inbox (durable path, survives laptop downtime):

        hord mobile pull /path/to/inbox/

    Both create capture cards (wh:cap) with immediate quad compilation.
    """
    pass


@mobile_cmd.command("serve")
@click.option("--port", "-p", default=7749, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--token", default=None,
              help="Auth token for API access (optional, recommended)")
@click.option("--scratch", is_flag=True,
              help="Append to scratch file instead of creating capture cards")
def serve_cmd(port, host, token, scratch):
    """Start the mobile capture HTTP server.

    Serves a capture form at http://<host>:<port>/ and accepts
    POST /capture with JSON, form data, or plain text.

    Bookmark the URL on your phone for one-tap access.
    Add to home screen as a PWA for app-like experience.

    Examples:

        hord mobile serve                    # default port 7749

        hord mobile serve -p 8080 --token s3cret

        hord mobile serve --scratch          # append to scratch file

    JSON API:

        curl -X POST http://localhost:7749/capture \\
          -H 'Content-Type: application/json' \\
          -d '{"content": "thought", "tags": "idea hoard"}'
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    CaptureHandler.hord_root = hord_root
    CaptureHandler.auth_token = token
    CaptureHandler.scratch_mode = scratch

    server = HTTPServer((host, port), CaptureHandler)

    click.echo(f"Mobile capture server running")
    click.echo(f"  URL: http://{host}:{port}/")
    click.echo(f"  Hord: {hord_root}")
    click.echo(f"  Mode: {'scratch' if scratch else 'capture cards'}")
    if token:
        click.echo(f"  Auth: Bearer token required for API")
    click.echo(f"  Press Ctrl+C to stop")
    click.echo()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")
        server.server_close()


@mobile_cmd.command("pull")
@click.argument("inbox_dir")
@click.option("--git-pull", "do_git_pull", is_flag=True,
              help="Run git pull in inbox_dir first")
@click.option("--archive/--delete", default=True,
              help="Archive processed files (default) or delete them")
@click.option("--verbose", "-v", is_flag=True)
def pull_cmd(inbox_dir, do_git_pull, archive, verbose):
    """Process captured files from a GitHub inbox directory.

    Reads .md, .txt, and .org files from INBOX_DIR, creates
    capture cards from each, then archives (or deletes) them.

    Designed to run from cron to process a git-synced inbox:

        # In crontab (every 5 minutes):
        cd /path/to/hord && hord mobile pull ~/hord-inbox/inbox/ --git-pull

    Inbox files can have optional YAML frontmatter:

        ---
        tags: idea hoard
        source: mobile
        title: My Thought
        ---
        The actual content goes here.

    Or just plain text — the first line becomes the title.

    Examples:

        hord mobile pull ~/hord-inbox/inbox/

        hord mobile pull ~/hord-inbox/inbox/ --git-pull -v

        hord mobile pull ~/hord-inbox/inbox/ --delete
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    inbox_dir = os.path.abspath(inbox_dir)

    if do_git_pull:
        # Find the git root of the inbox dir
        git_root = inbox_dir
        while git_root != "/" and not os.path.isdir(os.path.join(git_root, ".git")):
            git_root = os.path.dirname(git_root)

        if os.path.isdir(os.path.join(git_root, ".git")):
            if verbose:
                click.echo(f"  git pull in {git_root}")
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=git_root,
                capture_output=True, text=True)
            if result.returncode != 0:
                click.echo(f"  git pull failed: {result.stderr.strip()}",
                            err=True)
        else:
            click.echo(f"  Warning: {inbox_dir} is not in a git repo",
                        err=True)

    if not os.path.isdir(inbox_dir):
        click.echo(f"Error: directory not found: {inbox_dir}", err=True)
        raise SystemExit(1)

    processed = process_github_inbox(
        hord_root, inbox_dir,
        archive=archive,
        verbose=verbose)

    if processed:
        click.echo(f"Processed {processed} captures from inbox")
    else:
        click.echo("No new captures in inbox")


@mobile_cmd.command("setup")
def setup_cmd():
    """Print setup instructions for mobile capture.

    Shows how to configure your phone and laptop for both
    the HTTP server and GitHub inbox capture paths.
    """
    click.echo("""
Mobile Capture Setup
════════════════════

PATH A: HTTP Server (fast path, laptop must be running)
───────────────────────────────────────────────────────

  1. Start the server:

     cd /path/to/hord && hord mobile serve

  2. Find your laptop's local IP:

     hostname -I | awk '{print $1}'

  3. On your phone, bookmark: http://<laptop-ip>:7749/

  4. Optional: Add to home screen for PWA-like experience
     (Chrome → menu → "Add to Home screen")

  5. Optional: Use the HTTP Shortcuts app (Android, F-Droid)
     for one-tap capture without opening a browser:

     - Install: https://f-droid.org/packages/ch.rmy.android.http_shortcuts/
     - New shortcut → POST to http://<laptop-ip>:7749/capture
     - Content-Type: application/json
     - Body: {"content": "{input}", "tags": "", "source": "mobile"}
     - Add to home screen as widget


PATH B: GitHub Inbox (durable, survives laptop downtime)
────────────────────────────────────────────────────────

  1. Create a private GitHub repo (e.g. hord-inbox)

  2. Clone it on your laptop:

     git clone git@github.com:YOU/hord-inbox.git ~/hord-inbox
     mkdir -p ~/hord-inbox/inbox

  3. Add a cron job to process the inbox every 5 minutes:

     crontab -e
     */5 * * * * cd /path/to/hord && hord mobile pull ~/hord-inbox/inbox/ --git-pull

  4. On your phone, use HTTP Shortcuts (Android) to PUT files
     to the GitHub Contents API:

     - Generate a fine-grained PAT at github.com/settings/tokens
       (scope: Contents read/write on the inbox repo only)
     - New shortcut → PUT
     - URL: https://api.github.com/repos/YOU/hord-inbox/contents/inbox/{timestamp}.md
     - Headers: Authorization: Bearer YOUR_PAT
     - Body: {"message": "capture", "content": "{base64_of_input}"}

  5. Alternative: use GitHub mobile app to create files in inbox/

  6. Alternative: use Termux + git for offline capture


HYBRID (recommended)
────────────────────

  Set up both paths. HTTP Shortcuts can try the local server first
  and fall back to GitHub if it's unreachable. Your captures always
  land somewhere.
""")
