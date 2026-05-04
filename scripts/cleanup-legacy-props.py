#!/usr/bin/env python3
"""Cleanup legacy properties in hord cards.

Adds :TYPE: where missing (inferred from filename suffix).
Strips legacy properties: :NAME:, :VER:, :Stamp:, :Message-ID:, :Path:.
Strips legacy file-level directives: #+bibliography:

Run from the hord root:
  python3 scripts/cleanup-legacy-props.py [--dry-run] [--verbose]
"""

import os
import re
import sys


SUFFIX_TO_TYPE = {
    "3": "wh:pat",
    "4": "wh:con",
    "5": "wh:key",
    "6": "wh:wrk",
    "7": "wh:per",
    "8": "wh:cat",
    "9": "wh:sys",
    "10": "wh:pla",
    "11": "wh:evt",
    "12": "wh:obj",
    "13": "wh:org",
    "15": "wh:tag",
    "16": "wh:persona",
    "17": "wh:office",
    "18": "wh:task",
    "19": "wh:event",
}

LEGACY_PROPS = {
    "NAME", "VER", "Stamp", "Message-ID", "Path",
    "Name", "Ver", "STAMP", "MESSAGE-ID", "PATH",
}


def infer_type(filename):
    """Infer entity type from filename suffix."""
    basename = os.path.splitext(os.path.basename(filename))[0]
    # Match --N or —N at end
    for pattern in [r"--(\d+)$", r"\u2014(\d+)$"]:
        m = re.search(pattern, basename)
        if m:
            return SUFFIX_TO_TYPE.get(m.group(1))
    return None


def process_card(filepath, dry_run=False, verbose=False):
    """Process a single card. Returns status."""
    try:
        with open(filepath) as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return "error"

    if ":ID:" not in content:
        return "skip-no-id"

    original = content
    changes = []

    # Add :TYPE: if missing
    if ":TYPE:" not in content:
        entity_type = infer_type(filepath)
        if entity_type:
            # Insert after :ID: line
            content = re.sub(
                r"(:ID:\s+[0-9a-f-]+\n)",
                r"\1  :TYPE:      " + entity_type + "\n",
                content, count=1)
            changes.append(f"+TYPE:{entity_type}")

    # Strip legacy properties
    for prop in LEGACY_PROPS:
        pattern = re.compile(
            r"^\s*:" + re.escape(prop) + r":.*\n?",
            re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub("", content)
            changes.append(f"-{prop}")

    # Strip #+bibliography: lines
    if "#+bibliography:" in content:
        content = re.sub(r"^\#\+bibliography:.*\n?", "", content,
                         flags=re.MULTILINE)
        changes.append("-bibliography")

    if content == original:
        return "unchanged"

    if dry_run:
        if verbose:
            print(f"  WOULD  {os.path.basename(filepath)}: {', '.join(changes)}")
        return "would-modify"

    with open(filepath, "w") as f:
        f.write(content)

    if verbose:
        print(f"  OK     {os.path.basename(filepath)}: {', '.join(changes)}")

    return "modified"


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # Find hord root
    path = os.path.abspath(".")
    while path != "/":
        if os.path.isdir(os.path.join(path, ".hord")):
            break
        path = os.path.dirname(path)
    else:
        print("Error: not inside a hord.", file=sys.stderr)
        sys.exit(1)

    content_dir = os.path.join(path, "content")
    if not os.path.isdir(content_dir):
        print("Error: no content/ directory.", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        os.path.join(content_dir, f)
        for f in os.listdir(content_dir)
        if f.endswith(".org") and not f.startswith((".", "#")))

    print(f"Legacy property cleanup")
    print(f"  Hord: {path}")
    print(f"  Cards: {len(files)}")
    if dry_run:
        print(f"  Mode: DRY RUN")
    print()

    stats = {"modified": 0, "would-modify": 0, "unchanged": 0,
             "skip-no-id": 0, "error": 0}

    for filepath in files:
        status = process_card(filepath, dry_run, verbose)
        stats[status] = stats.get(status, 0) + 1

    print(f"\nResults:")
    if dry_run:
        print(f"  Would modify: {stats['would-modify']}")
    else:
        print(f"  Modified: {stats['modified']}")
    print(f"  Unchanged: {stats['unchanged']}")
    print(f"  No ID: {stats['skip-no-id']}")
    print(f"  Errors: {stats['error']}")

    if not dry_run and stats["modified"]:
        print(f"\nRun 'hord compile' to update quads.")


if __name__ == "__main__":
    main()
