"""hord search — full-text search across the hord."""

import os
import re

import click

from hord.git_utils import find_hord_root
from hord.quad import read_all_quads, find_all_quads_dirs, read_quads
from hord.vocab import Vocabulary, find_vocab
from hord.query import load_index


def search_hord(hord_root: str, text: str,
                tag_filter: str = "",
                type_filter: str = "",
                content_search: bool = False) -> list[dict]:
    """Search across titles, tags, and optionally file content.

    Returns list of dicts: {uuid, title, type, type_label, tags, path, match_in}.
    """
    index = load_index(hord_root)
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    text_lower = text.lower() if text else ""

    # Build uuid → path map from index
    uuid_to_path: dict[str, str] = {}
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("path\t"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    uuid_to_path[parts[1]] = parts[0]

    # Collect unique UUIDs
    seen = set()
    uuids = []
    for uuid in index.values():
        if uuid not in seen:
            seen.add(uuid)
            uuids.append(uuid)

    results = []

    for uuid in uuids:
        quads = read_all_quads(hord_root, uuid)
        if not quads:
            continue

        title = ""
        etype = ""
        tags = []
        for q in quads:
            if q.predicate == "v:title":
                title = q.object
            elif q.predicate == "v:type":
                etype = q.object
            elif q.predicate == "v:tag":
                tags.append(q.object)

        # Type filter
        if type_filter:
            type_label = vocab.label(etype) if vocab else etype
            tf = type_filter.lower()
            if tf not in etype.lower() and tf not in type_label.lower():
                continue

        # Tag filter
        if tag_filter:
            tf = tag_filter.lower()
            if not any(tf in t.lower() for t in tags):
                continue

        # Text search
        match_in = []
        if text_lower:
            if text_lower in title.lower():
                match_in.append("title")
            if any(text_lower in t.lower() for t in tags):
                match_in.append("tag")

            # Search file content
            if content_search:
                path = uuid_to_path.get(uuid)
                if path:
                    filepath = os.path.join(hord_root, path)
                    if os.path.exists(filepath):
                        with open(filepath, "r") as f:
                            file_content = f.read().lower()
                        if text_lower in file_content and "title" not in match_in:
                            match_in.append("content")

            if not match_in:
                continue

        type_label = vocab.label(etype) if vocab else etype
        results.append({
            "uuid": uuid,
            "title": title,
            "type": etype,
            "type_label": type_label,
            "tags": tags,
            "path": uuid_to_path.get(uuid, ""),
            "match_in": match_in,
        })

    # Sort: title matches first, then tag, then content
    def sort_key(r):
        if "title" in r["match_in"]:
            return (0, r["title"].lower())
        if "tag" in r["match_in"]:
            return (1, r["title"].lower())
        return (2, r["title"].lower())

    results.sort(key=sort_key)
    return results


@click.command("search")
@click.argument("text", required=False, default="")
@click.option("--tag", "-t", default="",
              help="Filter by tag")
@click.option("--type", "-T", "entity_type", default="",
              help="Filter by entity type (con, per, wrk, cap, tag, etc.)")
@click.option("--content", "-c", "search_content", is_flag=True,
              help="Also search inside file content (slower)")
def search_cmd(text, tag, entity_type, search_content):
    """Search the hord by title, tag, type, or content.

    Without text, lists all entities matching the filters.
    With text, searches titles and tags (add --content for full-text).

    Examples:

        hord search kanban

        hord search -t tps

        hord search -T cap

        hord search "production system" --content

        hord search -t hoard -T con
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord.", err=True)
        raise SystemExit(1)

    if not text and not tag and not entity_type:
        click.echo("Provide search text, --tag, or --type filter.", err=True)
        raise SystemExit(1)

    results = search_hord(
        hord_root, text,
        tag_filter=tag,
        type_filter=entity_type,
        content_search=search_content,
    )

    if not results:
        click.echo("No matches.")
        return

    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    for r in results:
        type_display = r["type_label"] or r["type"]
        tags_display = f"  [{', '.join(r['tags'])}]" if r["tags"] else ""
        match_display = f"  ({', '.join(r['match_in'])})" if r["match_in"] else ""
        click.echo(f"  {r['title']:<40} {type_display:<12}{tags_display}{match_display}")

    click.echo()
    click.echo(f"{len(results)} results")
