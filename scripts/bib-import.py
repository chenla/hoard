#!/usr/bin/env python3
"""Generate work cards from bib.bib for cited entries missing cards.

Usage:
    python bib-import.py [--dry-run] [--limit N] [--all]

By default, only creates cards for bib entries that are cited
somewhere in the hord but don't have a work card yet.

    --all      Create cards for ALL bib entries (not just cited ones)
    --dry-run  Show what would be created without writing files
    --limit N  Create at most N cards
"""

import argparse
import os
import re
import sys
import uuid
from datetime import datetime, timezone

# Add hoard src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from hord.new import slugify, TYPE_SUFFIX


def parse_bibtex(filepath):
    """Parse bib.bib into a dict of citekey -> fields."""
    entries = {}
    current_key = None
    current_fields = {}
    current_type = None

    with open(filepath) as f:
        content = f.read()

    # Match each entry: @type{key, ... }
    # We'll do a simple state-machine parse
    i = 0
    while i < len(content):
        # Find next @
        at_pos = content.find('@', i)
        if at_pos == -1:
            break

        # Match @type{key,
        m = re.match(r'@(\w+)\s*\{([^,]*),', content[at_pos:])
        if not m:
            i = at_pos + 1
            continue

        entry_type = m.group(1).lower()
        if entry_type == 'comment':
            i = at_pos + len(m.group(0))
            continue

        citekey = m.group(2).strip()
        fields = {'bib-type': entry_type}

        # Find the matching closing brace
        brace_start = at_pos + m.start() + content[at_pos:].index('{')
        depth = 1
        j = brace_start + 1
        while j < len(content) and depth > 0:
            if content[j] == '{':
                depth += 1
            elif content[j] == '}':
                depth -= 1
            j += 1

        entry_body = content[brace_start + 1:j - 1]

        # Parse fields from entry body
        field_pattern = re.compile(
            r'(\w[\w-]*)\s*=\s*'
        )
        pos = 0
        for fm in field_pattern.finditer(entry_body):
            field_name = fm.group(1).lower()
            val_start = fm.end()

            # Determine value delimiter
            if val_start >= len(entry_body):
                continue

            ch = entry_body[val_start:].lstrip()[0] if entry_body[val_start:].strip() else ''
            val_start = val_start + (len(entry_body[val_start:]) - len(entry_body[val_start:].lstrip()))

            if ch == '{':
                # Brace-delimited value
                d = 1
                k = val_start + 1
                while k < len(entry_body) and d > 0:
                    if entry_body[k] == '{':
                        d += 1
                    elif entry_body[k] == '}':
                        d -= 1
                    k += 1
                value = entry_body[val_start + 1:k - 1].strip()
            elif ch == '"':
                # Quote-delimited value
                k = val_start + 1
                while k < len(entry_body) and entry_body[k] != '"':
                    k += 1
                value = entry_body[val_start + 1:k].strip()
            else:
                # Bare value (number, etc)
                end = entry_body.find(',', val_start)
                if end == -1:
                    end = len(entry_body)
                value = entry_body[val_start:end].strip().rstrip('}')

            if value:
                fields[field_name] = value

        if citekey and citekey.strip():
            entries[citekey.strip()] = fields

        i = j

    return entries


def find_cited_keys(content_dir):
    """Find all citekeys referenced in org files."""
    cited = set()
    for fname in os.listdir(content_dir):
        if not fname.endswith('.org'):
            continue
        filepath = os.path.join(content_dir, fname)
        with open(filepath) as f:
            text = f.read()
        # Match cite:key patterns
        for m in re.finditer(r'cite:([^\s,\]\)]+)', text):
            cited.add(m.group(1))
    return cited


def find_existing_citekeys(content_dir):
    """Find citekeys that already have work cards."""
    existing = set()
    for fname in os.listdir(content_dir):
        if not fname.endswith('--6.org'):
            continue
        filepath = os.path.join(content_dir, fname)
        with open(filepath) as f:
            text = f.read()
        for m in re.finditer(r':CUSTOM_ID:\s+(\S+)', text):
            existing.add(m.group(1))
        # Also check ROAM_KEY
        for m in re.finditer(r'#\+ROAM_KEY:\s+cite:(\S+)', text):
            existing.add(m.group(1))
    return existing


def make_work_card(citekey, fields):
    """Generate an org-mode work card from bib fields."""
    title = fields.get('title', citekey)
    # Clean braces from title
    title = re.sub(r'[{}]', '', title)
    author = fields.get('author', '')
    year = fields.get('year', fields.get('date', ''))
    if re.match(r'(\d{4})', year):
        year = re.match(r'(\d{4})', year).group(1)
    publisher = fields.get('publisher', '')
    journal = fields.get('journal', fields.get('journaltitle', ''))
    doi = fields.get('doi', '')
    url = fields.get('url', '')
    bib_type = fields.get('bib-type', 'misc')

    card_uuid = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M")
    suffix = TYPE_SUFFIX.get("wh:wrk", "6")
    display_title = f"{title}\u2014{suffix}"
    slug = slugify(title)
    # Truncate long slugs (max 60 chars before suffix)
    if len(slug) > 60:
        slug = slug[:60].rstrip('_')
    filename = f"{slug}--{suffix}.org"

    # Build bib data properties
    bib_props = []
    if bib_type:
        bib_props.append(f"   :BIB-TYPE:    {bib_type}")
    if author:
        bib_props.append(f"   :AUTHOR:      {author}")
    if year:
        bib_props.append(f"   :YEAR:        {year}")
    if publisher:
        bib_props.append(f"   :PUBLISHER:   {publisher}")
    if journal:
        bib_props.append(f"   :JOURNAL:     {journal}")
    if doi:
        bib_props.append(f"   :DOI:         {doi}")
    if url:
        bib_props.append(f"   :URL:         {url}")
    bib_props.append(f"   :CITEKEY:     {citekey}")

    lines = [
        "#   -*- mode: org; fill-column: 60 -*-",
        "#+STARTUP: showall",
        f"#+TITLE:   {display_title}",
        '#+FILETAGS: "hord" "work"',
        f"#+bibliography: ~/proj/hord/bib/bib.bib",
        "",
        f"* {display_title}",
        "  :PROPERTIES:",
        f"  :ID:        {card_uuid}",
        "  :TYPE:      wh:wrk",
        f"  :CREATED:   {timestamp}",
        "  :LICENCE:   MIT/CC BY-SA 4.0",
        "  :END:",
        "",
        "** Relations",
        "   - TT :: [[id:e28106d4-c0ba-47ab-9b9b-5357bb3274ea][Work\u20148]]",
        f"   - PT :: {display_title}",
        "",
        "** Bibliographic Data",
        "   :PROPERTIES:",
        *bib_props,
        "   :END:",
        "",
        "** Notes",
        "",
        "",
        "** References",
        "",
        f"  - {author or 'Unknown'}, {title} ({year or 'n.d.'}).",
        f"    cite:{citekey}",
        "",
    ]
    return filename, "\n".join(lines), card_uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be created')
    parser.add_argument('--limit', type=int, default=0,
                        help='Max cards to create (0 = unlimited)')
    parser.add_argument('--all', action='store_true',
                        help='Create cards for all bib entries, not just cited ones')
    parser.add_argument('--hord', default=os.path.expanduser('~/proj/hord'),
                        help='Path to hord root')
    args = parser.parse_args()

    bib_path = os.path.join(args.hord, 'bib', 'bib.bib')
    content_dir = os.path.join(args.hord, 'content')

    if not os.path.exists(bib_path):
        print(f"Error: {bib_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {bib_path}...")
    entries = parse_bibtex(bib_path)
    print(f"  {len(entries)} bib entries")

    existing = find_existing_citekeys(content_dir)
    print(f"  {len(existing)} existing work cards")

    if args.all:
        candidates = set(entries.keys()) - existing
    else:
        cited = find_cited_keys(content_dir)
        print(f"  {len(cited)} cited entries across all cards")
        candidates = cited & set(entries.keys()) - existing
        print(f"  {len(candidates)} cited entries need work cards")

    if not candidates:
        print("Nothing to do.")
        return

    created = 0
    for citekey in sorted(candidates):
        if args.limit and created >= args.limit:
            break

        fields = entries[citekey]
        filename, content, card_uuid = make_work_card(citekey, fields)
        filepath = os.path.join(content_dir, filename)

        if os.path.exists(filepath):
            continue

        if args.dry_run:
            title = fields.get('title', citekey)
            title = re.sub(r'[{}]', '', title)
            print(f"  Would create: {filename}  [{title}]")
        else:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"  Created: {filename}")

        created += 1

    print(f"\n{'Would create' if args.dry_run else 'Created'} {created} work cards")


if __name__ == '__main__':
    main()
