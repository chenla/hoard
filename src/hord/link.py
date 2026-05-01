"""hord link — interactively build thesaurus relations between cards.

Create, list, and remove the thesaurus relations (BT, NT, RT, TT,
UF, PT, etc.) that form the semantic backbone of a hord.

Relations are written directly into the card's ** Relations section
(org) or relations frontmatter (md), then compiled into quads.
"""

import os
import re

import click

from hord.git_utils import find_hord_root
from hord.query import load_index, resolve_uuid_label, find_incoming
from hord.quad import read_all_quads, find_all_quads_dirs, read_quads
from hord.vocab import Vocabulary, find_vocab


# Valid thesaurus relation types
VALID_RELS = {
    "TT", "PT", "BT", "BTG", "BTI", "BTP",
    "NT", "NTG", "NTI", "NTP", "RT", "UF", "USE",
}

# Relations that take a UUID target (link to another card)
UUID_RELS = {"TT", "BT", "BTG", "BTI", "BTP", "NT", "NTG", "NTI", "NTP", "RT", "USE"}

# Relations that take a text label (not a card link)
TEXT_RELS = {"PT", "UF"}

# Inverse pairs — when you add BT from A→B, you can also add NT from B→A
INVERSE = {
    "BT": "NT", "NT": "BT",
    "BTG": "NTG", "NTG": "BTG",
    "BTI": "NTI", "NTI": "BTI",
    "BTP": "NTP", "NTP": "BTP",
    "UF": "USE", "USE": "UF",
    "RT": "RT",
}


def _resolve_term(term: str, index: dict) -> str:
    """Resolve a term (UUID, filename, partial UUID) to a full UUID."""
    # Direct match
    uuid = index.get(term)
    if uuid:
        return uuid

    # Partial UUID match
    for key, val in index.items():
        if key.startswith(term) and len(term) >= 4:
            return val

    # Case-insensitive filename match
    term_lower = term.lower().replace(" ", "_")
    for key, val in index.items():
        if key.lower().replace(" ", "_").startswith(term_lower) and not _looks_like_uuid(key):
            return val

    return ""


def _looks_like_uuid(s: str) -> bool:
    return len(s) == 36 and s.count("-") == 4


def _find_card_file(hord_root: str, uuid: str) -> str:
    """Find the source file path for a card UUID.

    Prefers .org files over .md when both exist (dual-format hords).
    """
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if not os.path.exists(index_path):
        return ""
    candidates = []
    with open(index_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and parts[1] == uuid:
                filepath = os.path.join(hord_root, parts[0])
                if os.path.exists(filepath):
                    candidates.append(filepath)
    if not candidates:
        return ""
    # Prefer .org over .md
    for c in candidates:
        if c.endswith(".org"):
            return c
    return candidates[0]


def _add_relation_org(filepath: str, rel_type: str,
                      target_uuid: str, target_label: str) -> bool:
    """Add a relation line to an org card's ** Relations section."""
    with open(filepath) as f:
        content = f.read()

    # Build the relation line
    if target_uuid:
        rel_line = f"   - {rel_type} :: [[id:{target_uuid}][{target_label}]]"
    else:
        rel_line = f"   - {rel_type} :: {target_label}"

    # Check if this exact relation already exists
    if rel_line in content:
        return False

    # Find ** Relations section
    rel_match = re.search(r"^\*\* Relations\s*$", content, re.MULTILINE)
    if rel_match:
        # Find the end of the relations section (next ** or end of file)
        after = content[rel_match.end():]
        next_section = re.search(r"^\*\* ", after, re.MULTILINE)
        if next_section:
            insert_pos = rel_match.end() + next_section.start()
        else:
            insert_pos = len(content)

        # Find last relation line before insert_pos to add after it
        section_text = content[rel_match.end():insert_pos]
        last_rel = None
        for m in re.finditer(r"   - \w+ :: .+\n?", section_text):
            last_rel = m

        if last_rel:
            actual_insert = rel_match.end() + last_rel.end()
            if not content[actual_insert - 1:actual_insert] == "\n":
                rel_line = "\n" + rel_line
            new_content = content[:actual_insert] + rel_line + "\n" + content[actual_insert:]
        else:
            # Empty relations section, add after the heading
            new_content = content[:rel_match.end()] + "\n" + rel_line + "\n" + content[rel_match.end():]
    else:
        # No Relations section — add one before ** Notes
        notes_match = re.search(r"^\*\* Notes", content, re.MULTILINE)
        if notes_match:
            insert = f"\n** Relations\n{rel_line}\n\n"
            new_content = content[:notes_match.start()] + insert + content[notes_match.start():]
        else:
            # Append at end
            new_content = content.rstrip() + f"\n\n** Relations\n{rel_line}\n"

    with open(filepath, "w") as f:
        f.write(new_content)
    return True


def _add_relation_md(filepath: str, rel_type: str,
                     target_uuid: str, target_label: str) -> bool:
    """Add a relation to a markdown card's frontmatter."""
    with open(filepath) as f:
        content = f.read()

    if not content.startswith("---"):
        return False

    end = content.find("\n---", 3)
    if end == -1:
        return False

    # Build relation string
    if target_uuid:
        rel_str = f'  - "{rel_type}: {target_uuid}  # {target_label}"'
    else:
        rel_str = f'  - "{rel_type}: {target_label}"'

    fm = content[4:end]
    body = content[end:]

    # Check for duplicate
    if rel_str.strip() in fm:
        return False

    # Find relations: section in frontmatter
    rel_match = re.search(r"^relations:", fm, re.MULTILINE)
    if rel_match:
        # Find end of relations list (next non-list-item line)
        after = fm[rel_match.end():]
        lines_after = after.split("\n")
        offset = 0
        for i, line in enumerate(lines_after):
            stripped = line.strip()
            if i == 0:
                # Same line as "relations:" — skip it
                offset += len(line) + 1
                continue
            if stripped.startswith("- "):
                offset += len(line) + 1
            elif stripped == "":
                offset += len(line) + 1
                break
            else:
                break

        insert_pos = 4 + rel_match.end() + offset
        # Ensure we insert on a new line
        if insert_pos > 0 and content[insert_pos - 1:insert_pos] != "\n":
            rel_str = "\n" + rel_str
        new_content = content[:insert_pos] + rel_str + "\n" + content[insert_pos:]
    else:
        # No relations section — add before closing ---
        new_content = content[:end] + "\nrelations:\n" + rel_str + "\n" + content[end:]

    with open(filepath, "w") as f:
        f.write(new_content)
    return True


def _remove_relation_org(filepath: str, rel_type: str,
                         target_uuid: str, target_label: str) -> bool:
    """Remove a relation from an org card."""
    with open(filepath) as f:
        content = f.read()

    # Match the relation line (with or without UUID link)
    if target_uuid:
        pattern = re.compile(
            rf"^   - {re.escape(rel_type)} :: \[\[id:{re.escape(target_uuid)}\]"
            rf"\[[^\]]*\]\]\s*\n?",
            re.MULTILINE)
    else:
        pattern = re.compile(
            rf"^   - {re.escape(rel_type)} :: {re.escape(target_label)}\s*\n?",
            re.MULTILINE)

    new_content, count = pattern.subn("", content)
    if count == 0:
        return False

    with open(filepath, "w") as f:
        f.write(new_content)
    return True


def _remove_relation_md(filepath: str, rel_type: str,
                        target_uuid: str, target_label: str) -> bool:
    """Remove a relation from a markdown card's frontmatter."""
    with open(filepath) as f:
        content = f.read()

    if target_uuid:
        pattern = re.compile(
            rf'^  - "{re.escape(rel_type)}: {re.escape(target_uuid)}.*"\s*\n?',
            re.MULTILINE)
    else:
        pattern = re.compile(
            rf'^  - "{re.escape(rel_type)}: {re.escape(target_label)}"\s*\n?',
            re.MULTILINE)

    new_content, count = pattern.subn("", content)
    if count == 0:
        return False

    with open(filepath, "w") as f:
        f.write(new_content)
    return True


def _list_relations(hord_root: str, uuid: str, vocab) -> list:
    """List all relations for a card (outgoing and incoming)."""
    results = []

    # Outgoing
    quads = read_all_quads(hord_root, uuid)
    rel_predicates = {
        "v:tt", "v:pt", "v:bt", "v:btg", "v:bti", "v:btp",
        "v:nt", "v:ntg", "v:nti", "v:ntp", "v:rt", "v:uf", "v:use",
    }
    for q in quads:
        if q.predicate in rel_predicates:
            label = vocab.label(q.predicate) if vocab else q.predicate
            if _looks_like_uuid(q.object):
                obj_label = resolve_uuid_label(hord_root, q.object, vocab)
                results.append(("out", label, obj_label, q.object))
            else:
                results.append(("out", label, q.object, ""))

    # Incoming
    incoming = find_incoming(hord_root, uuid)
    for q in incoming:
        if q.predicate in rel_predicates:
            label = vocab.label(q.predicate) if vocab else q.predicate
            subj_label = resolve_uuid_label(hord_root, q.subject, vocab)
            results.append(("in", label, subj_label, q.subject))

    return results


@click.group("link")
def link_cmd():
    """Manage thesaurus relations between cards.

    Build the semantic backbone of your hord by creating
    BT/NT/RT/TT/UF/PT relationships between cards.

    Examples:

        hord link add Kanban BT Lean_Manufacturing

        hord link add "Taiichi Ohno" RT Toyota_Production_System

        hord link add Kanban UF "看板"

        hord link show Kanban

        hord link remove Kanban BT Lean_Manufacturing

        hord link suggest Kanban
    """
    pass


@link_cmd.command("add")
@click.argument("source")
@click.argument("rel_type")
@click.argument("target")
@click.option("--reciprocal/--no-reciprocal", default=True,
              help="Also add inverse relation on target card (default: yes)")
@click.option("--verbose", "-v", is_flag=True)
def link_add(source, rel_type, target, reciprocal, verbose):
    """Add a thesaurus relation from SOURCE to TARGET.

    SOURCE and TARGET can be UUIDs, filenames, or partial UUIDs.
    REL_TYPE is one of: TT, PT, BT, BTG, BTI, BTP, NT, NTG,
    NTI, NTP, RT, UF, USE.

    For UF and PT, TARGET is a text label, not a card reference.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    rel_type = rel_type.upper()
    if rel_type not in VALID_RELS:
        click.echo(f"Error: unknown relation type '{rel_type}'", err=True)
        click.echo(f"Valid types: {', '.join(sorted(VALID_RELS))}", err=True)
        raise SystemExit(1)

    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    # Resolve source
    source_uuid = _resolve_term(source, index)
    if not source_uuid:
        click.echo(f"Error: could not find card '{source}'", err=True)
        raise SystemExit(1)

    source_file = _find_card_file(hord_root, source_uuid)
    if not source_file:
        click.echo(f"Error: source file not found for {source_uuid}", err=True)
        raise SystemExit(1)

    source_label = resolve_uuid_label(hord_root, source_uuid, vocab)

    # For text-only relations (UF, PT), target is the label itself
    if rel_type in TEXT_RELS:
        target_uuid = ""
        target_label = target
    else:
        target_uuid = _resolve_term(target, index)
        if not target_uuid:
            click.echo(f"Error: could not find card '{target}'", err=True)
            raise SystemExit(1)
        target_label = resolve_uuid_label(hord_root, target_uuid, vocab)

    # Add the relation
    is_org = source_file.endswith(".org")
    if is_org:
        added = _add_relation_org(source_file, rel_type, target_uuid, target_label)
    else:
        added = _add_relation_md(source_file, rel_type, target_uuid, target_label)

    if added:
        click.echo(f"  {source_label}")
        click.echo(f"    → {rel_type} → {target_label}")
    else:
        click.echo(f"  Relation already exists: {rel_type} → {target_label}")

    # Add reciprocal if applicable
    if reciprocal and rel_type in INVERSE and target_uuid:
        inv_type = INVERSE[rel_type]
        target_file = _find_card_file(hord_root, target_uuid)
        if target_file:
            if target_file.endswith(".org"):
                inv_added = _add_relation_org(target_file, inv_type, source_uuid, source_label)
            else:
                inv_added = _add_relation_md(target_file, inv_type, source_uuid, source_label)

            if inv_added:
                click.echo(f"  {target_label}")
                click.echo(f"    → {inv_type} → {source_label}")
            elif verbose:
                click.echo(f"  Reciprocal already exists: {inv_type} → {source_label}")

    click.echo("")
    click.echo("Run 'hord compile' to update quads.")


@link_cmd.command("remove")
@click.argument("source")
@click.argument("rel_type")
@click.argument("target")
@click.option("--reciprocal/--no-reciprocal", default=True,
              help="Also remove inverse relation on target card (default: yes)")
def link_remove(source, rel_type, target, reciprocal):
    """Remove a thesaurus relation from SOURCE to TARGET."""
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    rel_type = rel_type.upper()
    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    source_uuid = _resolve_term(source, index)
    if not source_uuid:
        click.echo(f"Error: could not find card '{source}'", err=True)
        raise SystemExit(1)

    source_file = _find_card_file(hord_root, source_uuid)
    if not source_file:
        click.echo(f"Error: source file not found", err=True)
        raise SystemExit(1)

    source_label = resolve_uuid_label(hord_root, source_uuid, vocab)

    if rel_type in TEXT_RELS:
        target_uuid = ""
        target_label = target
    else:
        target_uuid = _resolve_term(target, index)
        if not target_uuid:
            click.echo(f"Error: could not find card '{target}'", err=True)
            raise SystemExit(1)
        target_label = resolve_uuid_label(hord_root, target_uuid, vocab)

    is_org = source_file.endswith(".org")
    if is_org:
        removed = _remove_relation_org(source_file, rel_type, target_uuid, target_label)
    else:
        removed = _remove_relation_md(source_file, rel_type, target_uuid, target_label)

    if removed:
        click.echo(f"  Removed: {source_label} → {rel_type} → {target_label}")
    else:
        click.echo(f"  Relation not found")

    # Remove reciprocal
    if reciprocal and rel_type in INVERSE and target_uuid:
        inv_type = INVERSE[rel_type]
        target_file = _find_card_file(hord_root, target_uuid)
        if target_file:
            if target_file.endswith(".org"):
                _remove_relation_org(target_file, inv_type, source_uuid, source_label)
            else:
                _remove_relation_md(target_file, inv_type, source_uuid, source_label)

    click.echo("Run 'hord compile' to update quads.")


@link_cmd.command("show")
@click.argument("term")
def link_show(term):
    """Show all thesaurus relations for a card.

    Displays both outgoing and incoming relations.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    uuid = _resolve_term(term, index)
    if not uuid:
        click.echo(f"Not found: {term}", err=True)
        raise SystemExit(1)

    title = resolve_uuid_label(hord_root, uuid, vocab)
    click.echo(f"\n  {title}")
    click.echo(f"  {uuid}")
    click.echo(f"  {'─' * 50}")

    rels = _list_relations(hord_root, uuid, vocab)

    if not rels:
        click.echo("  No thesaurus relations.")
        return

    # Outgoing
    outgoing = [r for r in rels if r[0] == "out"]
    if outgoing:
        click.echo()
        click.echo("  Outgoing:")
        for _, pred, label, uid in outgoing:
            suffix = f"  ({uid[:8]}…)" if uid else ""
            click.echo(f"    {pred:>6}  → {label}{suffix}")

    # Incoming
    incoming = [r for r in rels if r[0] == "in"]
    if incoming:
        click.echo()
        click.echo("  Incoming:")
        for _, pred, label, uid in incoming:
            suffix = f"  ({uid[:8]}…)" if uid else ""
            click.echo(f"    {pred:>6}  ← {label}{suffix}")

    click.echo()


@link_cmd.command("suggest")
@click.argument("term")
@click.option("--limit", "-n", default=10,
              help="Maximum number of suggestions")
def link_suggest(term, limit):
    """Suggest possible relations for a card.

    Looks at the card's type, existing relations, and shared
    tags to find cards that might be related but aren't linked yet.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    uuid = _resolve_term(term, index)
    if not uuid:
        click.echo(f"Not found: {term}", err=True)
        raise SystemExit(1)

    title = resolve_uuid_label(hord_root, uuid, vocab)
    click.echo(f"\n  Suggestions for: {title}")
    click.echo(f"  {'─' * 50}")

    # Gather this card's properties
    my_quads = read_all_quads(hord_root, uuid)
    my_type = ""
    my_tags = set()
    my_linked = set()  # UUIDs already linked

    for q in my_quads:
        if q.predicate == "v:type":
            my_type = q.object
        elif q.predicate == "v:tag":
            my_tags.add(q.object.lower())
        elif _looks_like_uuid(q.object):
            my_linked.add(q.object)

    # Also check incoming
    for q in find_incoming(hord_root, uuid):
        my_linked.add(q.subject)

    # Score every other card by similarity
    # Collect all UUIDs from index
    all_uuids = set()
    for key, val in index.items():
        if _looks_like_uuid(val) and val != uuid:
            all_uuids.add(val)

    candidates = []
    for other_uuid in all_uuids:
        if other_uuid in my_linked:
            continue

        other_quads = read_all_quads(hord_root, other_uuid)
        score = 0
        other_type = ""
        other_tags = set()
        other_title = ""

        for q in other_quads:
            if q.predicate == "v:type":
                other_type = q.object
            elif q.predicate == "v:tag":
                other_tags.add(q.object.lower())
            elif q.predicate == "v:title":
                other_title = q.object

        # Same type = mild signal
        if other_type == my_type:
            score += 1

        # Shared tags = strong signal
        shared = my_tags & other_tags
        score += len(shared) * 3

        # Title word overlap (basic)
        my_words = set(title.lower().split())
        other_words = set(other_title.lower().split())
        # Remove common stop words
        stop = {"the", "a", "an", "of", "and", "in", "to", "for", "is", "on", "at"}
        my_words -= stop
        other_words -= stop
        word_overlap = my_words & other_words
        score += len(word_overlap) * 2

        if score > 0:
            suggested_rel = "RT"
            if other_type == my_type:
                suggested_rel = "RT"
            candidates.append((score, other_title, other_uuid, suggested_rel, shared))

    candidates.sort(reverse=True, key=lambda x: x[0])

    if not candidates:
        click.echo("  No suggestions found. Add more cards or tags.")
        return

    for score, otitle, ouid, srel, shared in candidates[:limit]:
        tags_str = f" (tags: {', '.join(shared)})" if shared else ""
        click.echo(f"    {srel}  {otitle}{tags_str}")
        click.echo(f"         hord link add {term} {srel} {ouid[:8]}")

    click.echo()
