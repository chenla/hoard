#!/usr/bin/env python3
"""WEMI Phase 1 — conservative batch annotation of wh:wrk cards.

Reads existing work cards and adds WEMI metadata properties
without requiring judgment or external lookups.

What it does:
  - Adds :DATE-EXPR: from the existing :YEAR: (conservative —
    BibTeX years usually reflect the cited edition)
  - Adds :DATE-WHOLE: as empty (for Phase 2 lookup to fill)
  - Adds :WEMI: W (marks that WEMI assessment has touched this card)
  - Adds :MANIFESTATIONS: count of matching blobs in lib/blob/
  - Reports statistics

What it does NOT do:
  - Guess original publication dates (that's Phase 2)
  - Create separate E/M/I cards (E&M are metadata, not containers)
  - Modify any existing properties
  - Touch cards that already have :WEMI: set

Run from the hord root:
  python3 scripts/wemi-phase1.py [--dry-run] [--verbose]
"""

import os
import re
import sys


def find_hord_root():
    """Walk up to find .hord/ directory."""
    path = os.path.abspath(".")
    while path != "/":
        if os.path.isdir(os.path.join(path, ".hord")):
            return path
        path = os.path.dirname(path)
    return None


def find_blobs_for_citekey(blob_dir, citekey):
    """Find blob files matching a citekey."""
    if not citekey or not os.path.isdir(blob_dir):
        return []
    # Normalise: citekeys use colon, some filenames use space
    matches = []
    ck_pattern = re.compile(
        "^" + re.escape(citekey).replace("\\:", "[: ]") + r"\.",
        re.IGNORECASE)
    for fname in os.listdir(blob_dir):
        if ck_pattern.match(fname):
            matches.append(fname)
    return sorted(matches)


def extract_citekey(content):
    """Extract citekey from a card, trying multiple formats."""
    # New format: :CITEKEY: in Bibliographic Data
    m = re.search(r":CITEKEY:\s+(\S+?)(?:,?\s*$)", content, re.MULTILINE)
    if m:
        return m.group(1).strip().rstrip(",")

    # Legacy: :CUSTOM_ID: in Notes
    m = re.search(r":CUSTOM_ID:\s+(\S+)", content)
    if m:
        return m.group(1).strip()

    # Legacy: #+ROAM_KEY: cite:key
    m = re.search(r"#\+ROAM_KEY:\s+cite:(\S+)", content)
    if m:
        return m.group(1).strip()

    return ""


def extract_year(content):
    """Extract year from a card."""
    m = re.search(r":YEAR:\s+(\d{4})", content)
    if m:
        return m.group(1)
    return ""


def extract_author(content):
    """Extract author from a card."""
    m = re.search(r":AUTHOR:\s+(.+)", content)
    if m:
        return m.group(1).strip()
    return ""


def extract_publisher(content):
    """Extract publisher from a card."""
    m = re.search(r":PUBLISHER:\s+(.+)", content)
    if m:
        val = m.group(1).strip()
        if val and val != "nil":
            return val
    return ""


def has_wemi(content):
    """Check if card already has WEMI annotation."""
    return bool(re.search(r":WEMI:", content))


def find_main_property_drawer(content):
    """Find the main H1 property drawer (the card's identity drawer).

    Returns (start, end, indent) or None.
    We want the first :PROPERTIES:/:END: block that contains :ID:.
    Handles inconsistent indentation between PROPERTIES and END.
    """
    # Find all :PROPERTIES: starts
    props_starts = [m.start() for m in re.finditer(
        r"^\s*:PROPERTIES:\s*$", content, re.MULTILINE)]

    for ps in props_starts:
        # Find the matching :END:
        end_match = re.search(r"^\s*:END:\s*$", content[ps+1:], re.MULTILINE)
        if not end_match:
            continue
        end_pos = ps + 1 + end_match.end()
        block = content[ps:end_pos]
        if ":ID:" in block:
            # Determine indent from the :PROPERTIES: line
            line_start = content.rfind("\n", 0, ps) + 1
            indent = content[line_start:ps]
            return ps, end_pos, indent

    return None


def add_wemi_properties(content, year, blob_count):
    """Add WEMI properties to the card's main property drawer.

    Inserts before :END: of the identity property drawer.
    """
    result = find_main_property_drawer(content)
    if result is None:
        return content, False

    start, end, indent = result

    # Find the :END: line within this drawer
    # We need to insert just before :END:
    drawer_text = content[start:end]
    end_match = re.search(r"^(\s*):END:\s*$", drawer_text, re.MULTILINE)
    if not end_match:
        return content, False

    insert_pos = start + end_match.start()

    # Build new properties
    new_props = []
    if year:
        new_props.append(f"{indent}:DATE-EXPR:   {year}")
    new_props.append(f"{indent}:DATE-WHOLE:")
    new_props.append(f"{indent}:WEMI:        W")
    if blob_count > 0:
        new_props.append(f"{indent}:MANIFESTATIONS: {blob_count}")

    new_text = "\n".join(new_props) + "\n"
    new_content = content[:insert_pos] + new_text + content[insert_pos:]
    return new_content, True


def process_card(filepath, blob_dir, dry_run=False, verbose=False):
    """Process a single work card. Returns status string."""
    try:
        with open(filepath) as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return "error"

    if has_wemi(content):
        return "skip-has-wemi"

    if ":TYPE:" in content and "wh:wrk" not in content:
        # New-format card but not a work
        return "skip-not-work"

    year = extract_year(content)
    citekey = extract_citekey(content)
    author = extract_author(content)
    blobs = find_blobs_for_citekey(blob_dir, citekey)

    new_content, modified = add_wemi_properties(content, year, len(blobs))

    if not modified:
        return "skip-no-drawer"

    if dry_run:
        if verbose:
            fname = os.path.basename(filepath)
            print(f"  WOULD  {fname}")
            print(f"         year={year} citekey={citekey} blobs={len(blobs)}")
        return "would-modify"

    with open(filepath, "w") as f:
        f.write(new_content)

    if verbose:
        fname = os.path.basename(filepath)
        print(f"  OK     {fname}")
        print(f"         year={year} citekey={citekey} blobs={len(blobs)}")

    return "modified"


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    hord_root = find_hord_root()
    if not hord_root:
        print("Error: not inside a hord.", file=sys.stderr)
        sys.exit(1)

    content_dir = os.path.join(hord_root, "content")
    blob_dir = os.path.join(hord_root, "lib", "blob")

    if not os.path.isdir(content_dir):
        print("Error: no content/ directory.", file=sys.stderr)
        sys.exit(1)

    # Collect work cards
    work_files = sorted(
        os.path.join(content_dir, f)
        for f in os.listdir(content_dir)
        if (f.endswith("--6.org") or f.endswith("\u20146.org"))
        and not f.startswith((".", "#")))

    print(f"WEMI Phase 1: conservative annotation")
    print(f"  Hord: {hord_root}")
    print(f"  Work cards: {len(work_files)}")
    print(f"  Blob dir: {blob_dir} ({'exists' if os.path.isdir(blob_dir) else 'MISSING'})")
    if dry_run:
        print(f"  Mode: DRY RUN")
    print()

    stats = {
        "modified": 0,
        "would-modify": 0,
        "skip-has-wemi": 0,
        "skip-not-work": 0,
        "skip-no-drawer": 0,
        "error": 0,
    }

    # Track blob coverage
    total_with_blobs = 0
    total_blobs_found = 0

    for filepath in work_files:
        status = process_card(filepath, blob_dir, dry_run, verbose)
        stats[status] = stats.get(status, 0) + 1

        # Count blob matches for stats
        try:
            with open(filepath) as f:
                content = f.read()
            ck = extract_citekey(content)
            blobs = find_blobs_for_citekey(blob_dir, ck)
            if blobs:
                total_with_blobs += 1
                total_blobs_found += len(blobs)
        except:
            pass

    print(f"\nResults:")
    if dry_run:
        print(f"  Would modify: {stats['would-modify']}")
    else:
        print(f"  Modified: {stats['modified']}")
    print(f"  Already has WEMI: {stats['skip-has-wemi']}")
    print(f"  No property drawer: {stats['skip-no-drawer']}")
    print(f"  Errors: {stats['error']}")

    print(f"\nBlob coverage:")
    print(f"  Cards with matching blobs: {total_with_blobs} / {len(work_files)}")
    print(f"  Total blob files matched: {total_blobs_found}")
    remaining = len(work_files) - total_with_blobs
    print(f"  Cards without blobs: {remaining}")

    if not dry_run and stats["modified"]:
        print(f"\nNext steps:")
        print(f"  hord compile    # regenerate quads with WEMI predicates")
        print(f"  hord status     # verify")


if __name__ == "__main__":
    main()
