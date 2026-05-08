"""Holon parsing and compilation — extract membership, expression
preference, and ordering from wh:holon card bodies."""

import os
import re
from dataclasses import dataclass, field

from hord.quad import (
    Quad, write_quads, quad_path, read_quads,
    overlay_for_predicate, find_all_quads_dirs,
)


@dataclass
class HolonDef:
    """Parsed holon definition from a wh:holon card body."""
    uuid: str
    title: str
    # Membership
    member_slugs: list[str] = field(default_factory=list)
    member_uuids: list[str] = field(default_factory=list)
    member_tag: str | None = None
    # Expression preference
    expr_prefer: str | None = None
    expr_fallback: str = "whole"  # "whole" or "omit"
    # Ordering: list of (type_filter, sort_key) tuples
    order_rules: list[tuple[str, str]] = field(default_factory=list)


def parse_holon_body(filepath: str, uuid: str, title: str) -> HolonDef:
    """Parse the Membership, Expression, and Order sections from a
    wh:holon card's org or markdown body."""

    holon = HolonDef(uuid=uuid, title=title)

    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    section = None  # current section being parsed

    for line in lines:
        stripped = line.strip()

        # Detect org headings (** Membership, ** Expression, ** Order)
        if re.match(r"^\*{1,3}\s+Membership", stripped, re.IGNORECASE):
            section = "membership"
            continue
        elif re.match(r"^\*{1,3}\s+Expression", stripped, re.IGNORECASE):
            section = "expression"
            continue
        elif re.match(r"^\*{1,3}\s+Order", stripped, re.IGNORECASE):
            section = "order"
            continue
        # Detect markdown headings
        elif re.match(r"^#{1,3}\s+Membership", stripped, re.IGNORECASE):
            section = "membership"
            continue
        elif re.match(r"^#{1,3}\s+Expression", stripped, re.IGNORECASE):
            section = "expression"
            continue
        elif re.match(r"^#{1,3}\s+Order", stripped, re.IGNORECASE):
            section = "order"
            continue
        # Any other heading resets section
        elif re.match(r"^(\*{1,3}|#{1,3})\s+", stripped):
            section = None
            continue

        if not stripped:
            continue

        if section == "membership":
            _parse_membership_line(stripped, holon)
        elif section == "expression":
            _parse_expression_line(stripped, holon)
        elif section == "order":
            _parse_order_line(stripped, holon)

    return holon


# UUID regex for matching explicit UUIDs in membership lists
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# Tag membership: "Cards tagged ~foo" or "tagged ~foo"
TAG_RE = re.compile(r"tagged\s+~(\S+)", re.IGNORECASE)

# Org ID link: [[id:UUID][Label]]
ID_LINK_RE = re.compile(r"\[\[id:([0-9a-f-]+)\]\[([^\]]*)\]\]")


def _parse_membership_line(line: str, holon: HolonDef) -> None:
    """Parse a single line from the Membership section."""
    # Check for tag-based membership
    tag_match = TAG_RE.search(line)
    if tag_match:
        holon.member_tag = tag_match.group(1).rstrip(",")
        return

    # Check for org ID link
    link_match = ID_LINK_RE.search(line)
    if link_match:
        holon.member_uuids.append(link_match.group(1))
        return

    # Check for explicit UUID
    uuid_match = UUID_RE.search(line)
    if uuid_match:
        holon.member_uuids.append(uuid_match.group(0))
        return

    # Check for list item with slug: "- slug-name (wh:type)" or "- slug-name"
    list_match = re.match(r"^-\s+(\S+)", line)
    if list_match:
        slug = list_match.group(1)
        # Skip if it looks like a sentence or the "plus:" line
        if slug.lower() not in ("cards", "plus:") and not slug.startswith("("):
            holon.member_slugs.append(slug)


def _parse_expression_line(line: str, holon: HolonDef) -> None:
    """Parse a single line from the Expression section."""
    lower = line.lower()
    if lower.startswith("prefer:"):
        holon.expr_prefer = line.split(":", 1)[1].strip()
    elif lower.startswith("fallback:"):
        val = line.split(":", 1)[1].strip().lower()
        if val in ("whole", "omit"):
            holon.expr_fallback = val


def _parse_order_line(line: str, holon: HolonDef) -> None:
    """Parse a single line from the Order section.

    Expected format: '1. wh:per (alphabetical by title)' or '2. wh:evt'
    """
    m = re.match(r"^\d+\.\s+(wh:\w+)(?:\s*\((.+?)\))?", line)
    if m:
        type_filter = m.group(1)
        sort_key = m.group(2) if m.group(2) else "alphabetical by title"
        holon.order_rules.append((type_filter, sort_key))


def resolve_slug_to_uuid(slug: str, index: dict[str, str]) -> str | None:
    """Resolve a card slug to its UUID using the index.

    The index maps basenames (without extension) to UUIDs.
    Tries the slug as-is first, then common suffix patterns.
    """
    # Direct match on basename
    if slug in index:
        return index[slug]

    # Try with common suffixes
    for suffix in range(3, 22):
        candidate = f"{slug}--{suffix}"
        if candidate in index:
            return index[candidate]

    return None


def build_basename_index(hord_root: str) -> dict[str, str]:
    """Build a basename → UUID index from .hord/index.tsv."""
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    index = {}
    if not os.path.exists(index_path):
        return index
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("path\t"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                path, uuid = parts[0], parts[1]
                # Store by basename without extension
                basename = os.path.splitext(os.path.basename(path))[0]
                index[basename] = uuid
    return index


def find_cards_with_tag(hord_root: str, tag: str) -> list[str]:
    """Find all card UUIDs that have a v:tag quad matching the given tag."""
    uuids = []
    for quads_dir in find_all_quads_dirs(hord_root):
        for prefix_dir in _list_prefix_dirs(quads_dir):
            for fname in os.listdir(prefix_dir):
                if not fname.endswith(".tsv"):
                    continue
                fpath = os.path.join(prefix_dir, fname)
                for quad in read_quads(fpath):
                    if quad.predicate == "v:tag" and quad.object == tag:
                        uuids.append(quad.subject)
    return uuids


def find_expression_for(hord_root: str, whole_uuid: str,
                        expr_tag: str) -> str | None:
    """Find an expression card UUID for a Whole, matching the given tag.

    Looks for cards that have both:
    - v:s-eo pointing to whole_uuid (in strata overlay)
    - v:tag matching expr_tag (in structural overlay)
    """
    # First find all cards that are expressions of this whole
    expr_uuids = []
    strata_dir = os.path.join(hord_root, ".hord", "overlays", "strata", "quads")
    if os.path.isdir(strata_dir):
        for prefix_dir in _list_prefix_dirs(strata_dir):
            for fname in os.listdir(prefix_dir):
                if not fname.endswith(".tsv"):
                    continue
                fpath = os.path.join(prefix_dir, fname)
                for quad in read_quads(fpath):
                    if quad.predicate == "v:s-eo" and quad.object == whole_uuid:
                        expr_uuids.append(quad.subject)

    if not expr_uuids:
        return None

    # Now check which of those expressions has the matching tag
    for expr_uuid in expr_uuids:
        structural_path = quad_path(hord_root, expr_uuid, overlay="structural")
        for quad in read_quads(structural_path):
            if quad.predicate == "v:tag" and quad.object == expr_tag:
                return expr_uuid

    return None


def _list_prefix_dirs(quads_dir: str) -> list[str]:
    """List UUID prefix subdirectories within a quads directory."""
    if not os.path.isdir(quads_dir):
        return []
    dirs = []
    for name in os.listdir(quads_dir):
        full = os.path.join(quads_dir, name)
        if os.path.isdir(full):
            dirs.append(full)
    return dirs


def compile_holon(holon: HolonDef, hord_root: str,
                  context: str, verbose: bool = False) -> list[Quad]:
    """Generate quads for a holon definition.

    Must be called AFTER the first compile pass so that the index
    and tag quads exist for resolution.

    Returns the list of generated quads (already written to disk).
    """
    basename_index = build_basename_index(hord_root)
    quads = []

    # Resolve all members to UUIDs
    resolved_uuids = set()

    # Explicit UUIDs
    for uuid in holon.member_uuids:
        resolved_uuids.add(uuid)

    # Slug-based members
    for slug in holon.member_slugs:
        uuid = resolve_slug_to_uuid(slug, basename_index)
        if uuid:
            resolved_uuids.add(uuid)
        elif verbose:
            import click
            click.echo(f"  Warning: holon '{holon.title}' — "
                       f"could not resolve slug '{slug}'")

    # Tag-based members
    if holon.member_tag:
        tagged = find_cards_with_tag(hord_root, holon.member_tag)
        for uuid in tagged:
            # Don't include the holon card itself
            if uuid != holon.uuid:
                resolved_uuids.add(uuid)

    # Filter out expression cards — they appear via substitution, not
    # as standalone members.  An expression card has a v:s-eo quad.
    expression_uuids = set()
    for uuid in list(resolved_uuids):
        if _is_expression_card(hord_root, uuid):
            expression_uuids.add(uuid)
    resolved_uuids -= expression_uuids

    # Generate v:h-member quads
    for member_uuid in sorted(resolved_uuids):
        quads.append(Quad(
            subject=holon.uuid,
            predicate="v:h-member",
            object=member_uuid,
            context=context,
        ))

    # Generate v:h-expr quad
    if holon.expr_prefer:
        quads.append(Quad(
            subject=holon.uuid,
            predicate="v:h-expr",
            object=holon.expr_prefer,
            context=context,
        ))

    # Generate v:h-order quads
    # Assign order positions based on type rules, then sort within type
    position = 1
    for type_filter, sort_key in holon.order_rules:
        # Find members of this type
        type_members = []
        for member_uuid in resolved_uuids:
            member_type = _get_card_type(hord_root, member_uuid)
            if member_type == type_filter:
                member_title = _get_card_title(hord_root, member_uuid)
                type_members.append((member_uuid, member_title or ""))

        # Sort within type group
        type_members.sort(key=lambda x: x[1].lower())

        for member_uuid, _ in type_members:
            quads.append(Quad(
                subject=member_uuid,
                predicate="v:h-order",
                object=str(position),
                context=holon.uuid,  # holon UUID as context
            ))
            position += 1

    # Any members not covered by order rules get appended at the end
    ordered_uuids = {q.subject for q in quads if q.predicate == "v:h-order"}
    for member_uuid in sorted(resolved_uuids - ordered_uuids):
        quads.append(Quad(
            subject=member_uuid,
            predicate="v:h-order",
            object=str(position),
            context=holon.uuid,
        ))
        position += 1

    # Write holon quads to structural overlay
    # Read existing non-holon quads (e.g. tags from first pass),
    # replace any previous holon quads, then write.
    if quads:
        qpath = quad_path(hord_root, holon.uuid, overlay="structural")
        existing = read_quads(qpath)
        # Keep only non-holon quads from the existing file
        holon_preds = {"v:h-member", "v:h-expr", "v:h-order", "v:h-cascade"}
        kept = [q for q in existing if q.predicate not in holon_preds]
        write_quads(qpath, kept + quads)

    return quads


def _is_expression_card(hord_root: str, uuid: str) -> bool:
    """Check if a card is an expression (has a v:s-eo quad)."""
    qpath = quad_path(hord_root, uuid, overlay="strata")
    for quad in read_quads(qpath):
        if quad.predicate == "v:s-eo":
            return True
    return False


def _get_card_type(hord_root: str, uuid: str) -> str | None:
    """Look up a card's v:type from the strata overlay."""
    qpath = quad_path(hord_root, uuid, overlay="strata")
    for quad in read_quads(qpath):
        if quad.predicate == "v:type":
            return quad.object
    return None


def _get_card_title(hord_root: str, uuid: str) -> str | None:
    """Look up a card's v:title from the strata overlay."""
    qpath = quad_path(hord_root, uuid, overlay="strata")
    for quad in read_quads(qpath):
        if quad.predicate == "v:title":
            return quad.object
    return None
