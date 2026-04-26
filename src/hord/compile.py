"""hord compile — parse org and markdown files into quads and build the index."""

import os

import click

from hord.git_utils import find_hord_root, blob_hash
from hord.org_parser import parse_org_file
from hord.org_parser import scan_directory as scan_org
from hord.md_parser import parse_md_file
from hord.md_parser import scan_directory as scan_md
from hord.quad import Quad, write_quads, quad_path
from hord.vocab import Vocabulary, find_vocab


# Map relation type labels to vocab term IDs
REL_TO_PREDICATE = {
    "TT": "v:tt",
    "PT": "v:pt",
    "BT": "v:bt",
    "BTG": "v:btg",
    "BTI": "v:bti",
    "BTP": "v:btp",
    "NT": "v:nt",
    "NTG": "v:ntg",
    "NTI": "v:nti",
    "NTP": "v:ntp",
    "RT": "v:rt",
    "UF": "v:uf",
    "USE": "v:use",
    "WO": "v:s-wo",
    "EO": "v:s-eo",
    "MO": "v:s-mo",
    "IO": "v:s-io",
}


@click.command("compile")
@click.argument("path", default=".")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def compile_cmd(path, verbose):
    """Compile org-mode files into Hoard quads.

    Scans PATH for .org files, extracts metadata (UUIDs, types,
    thesaurus relationships), and writes quad files to .hord/quads/.
    Updates .hord/index.tsv with path-to-UUID mappings.

    PATH defaults to the current directory.
    """
    hord_root = find_hord_root(".")
    if hord_root is None:
        click.echo("Error: not inside a hord. Run 'hord init' first.", err=True)
        raise SystemExit(1)

    # Resolve path relative to hord root
    scan_path = os.path.abspath(path)
    if not os.path.exists(scan_path):
        click.echo(f"Error: path does not exist: {scan_path}", err=True)
        raise SystemExit(1)

    # Load vocabulary for validation
    vocab_path = find_vocab(hord_root)
    vocab = Vocabulary.load(vocab_path) if vocab_path else None

    # Scan for org and markdown files
    if os.path.isfile(scan_path):
        if scan_path.endswith(".md"):
            records = [parse_md_file(scan_path)]
        else:
            records = [parse_org_file(scan_path)]
        records = [r for r in records if r.is_valid]
    else:
        records = scan_org(scan_path) + scan_md(scan_path)

    if not records:
        click.echo("No valid org records found.")
        return

    # Build index and quads
    index_entries = []
    total_quads = 0
    files_compiled = 0

    for record in records:
        if not record.uuid:
            continue

        # Compute blob hash for provenance
        try:
            context = blob_hash(record.filepath)
        except Exception:
            context = "unknown"

        # Build quads for this entity
        quads = []

        # Type quad
        if record.entity_type:
            quads.append(Quad(
                subject=record.uuid,
                predicate="v:type",
                object=record.entity_type,
                context=context,
            ))

        # Title quad
        if record.title:
            quads.append(Quad(
                subject=record.uuid,
                predicate="v:title",
                object=record.title,
                context=context,
            ))

        # Author quad
        if record.author:
            quads.append(Quad(
                subject=record.uuid,
                predicate="v:author",
                object=record.author,
                context=context,
            ))

        # Relation quads
        for rel in record.relations:
            predicate = REL_TO_PREDICATE.get(rel.rel_type)
            if not predicate:
                if verbose:
                    click.echo(f"  Warning: unknown relation type '{rel.rel_type}' in {record.filepath}")
                continue

            if rel.target_uuid:
                obj = rel.target_uuid
            else:
                obj = rel.target_label

            quads.append(Quad(
                subject=record.uuid,
                predicate=predicate,
                object=obj,
                context=context,
            ))

        # UF quads from ROAM_ALIASES
        for alias in record.aliases:
            quads.append(Quad(
                subject=record.uuid,
                predicate="v:uf",
                object=alias,
                context=context,
            ))

        # Write quad file
        qpath = quad_path(hord_root, record.uuid)
        write_quads(qpath, quads)
        total_quads += len(quads)
        files_compiled += 1

        # Index entry
        relpath = os.path.relpath(record.filepath, hord_root)
        index_entries.append((relpath, record.uuid))

        if verbose:
            click.echo(f"  {relpath} → {len(quads)} quads")

    # Write index.tsv
    index_path = os.path.join(hord_root, ".hord", "index.tsv")
    with open(index_path, "w") as f:
        f.write("path\tuuid\n")
        for p, u in sorted(index_entries):
            f.write(f"{p}\t{u}\n")

    click.echo(f"Compiled {files_compiled} files → {total_quads} quads")
    click.echo(f"Index: {len(index_entries)} entries")
