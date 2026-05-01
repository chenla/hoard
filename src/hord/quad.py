"""Quad store primitives — read, write, and validate TSV quads."""

import os
from dataclasses import dataclass


@dataclass
class Quad:
    subject: str
    predicate: str
    object: str
    context: str

    def to_tsv(self) -> str:
        return f"{self.subject}\t{self.predicate}\t{self.object}\t{self.context}"

    @classmethod
    def from_tsv(cls, line: str) -> "Quad":
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 4:
            raise ValueError(f"Expected 4 tab-separated fields, got {len(parts)}: {line!r}")
        return cls(subject=parts[0], predicate=parts[1],
                   object=parts[2], context=parts[3])


def read_quads(filepath: str) -> list[Quad]:
    """Read quads from a TSV file. Skips the header line and comments."""
    quads = []
    if not os.path.exists(filepath):
        return quads
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Skip header
            if line.startswith("subject\t"):
                continue
            quads.append(Quad.from_tsv(line))
    return quads


def write_quads(filepath: str, quads: list[Quad]) -> None:
    """Write quads to a TSV file, overwriting any existing content."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write("subject\tpredicate\tobject\tcontext\n")
        for q in quads:
            f.write(q.to_tsv() + "\n")


def append_quads(filepath: str, quads: list[Quad]) -> None:
    """Append quads to an existing TSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    exists = os.path.exists(filepath)
    with open(filepath, "a") as f:
        if not exists:
            f.write("subject\tpredicate\tobject\tcontext\n")
        for q in quads:
            f.write(q.to_tsv() + "\n")


def quad_path(hord_root: str, uuid: str, overlay: str | None = None) -> str:
    """Return the filesystem path for a node's quad file.
    Sharded by first 4 chars of UUID.
    If overlay is given, returns path under .hord/overlays/<overlay>/quads/.
    Otherwise returns the legacy path under .hord/quads/."""
    prefix = uuid[:4]
    if overlay:
        return os.path.join(hord_root, ".hord", "overlays", overlay,
                            "quads", prefix, f"{uuid}.tsv")
    return os.path.join(hord_root, ".hord", "quads", prefix, f"{uuid}.tsv")


# Predicate → overlay routing
STRATA_PREDICATES = {
    "v:type", "v:title", "v:author",
    "v:s-wo", "v:s-eo", "v:s-mo", "v:s-io", "v:s-type",
}

STRUCTURAL_PREDICATES = {
    "v:tt", "v:pt", "v:bt", "v:btg", "v:bti", "v:btp",
    "v:nt", "v:ntg", "v:nti", "v:ntp",
    "v:rt", "v:uf", "v:use",
}


def overlay_for_predicate(predicate: str) -> str:
    """Return the overlay name for a given predicate."""
    if predicate in STRATA_PREDICATES:
        return "strata"
    if predicate in STRUCTURAL_PREDICATES:
        return "structural"
    # Default: structural for unknown predicates
    return "structural"


def list_overlays(hord_root: str) -> list[str]:
    """Return list of overlay names found under .hord/overlays/."""
    overlays_dir = os.path.join(hord_root, ".hord", "overlays")
    if not os.path.isdir(overlays_dir):
        return []
    return sorted(
        d for d in os.listdir(overlays_dir)
        if os.path.isdir(os.path.join(overlays_dir, d, "quads"))
    )


def read_all_quads(hord_root: str, uuid: str,
                   overlays: list[str] | None = None) -> list[Quad]:
    """Read and compose quads for a UUID across all (or specified) overlays.
    Falls back to legacy .hord/quads/ if no overlays exist."""
    available = list_overlays(hord_root)
    if not available:
        # Legacy mode: single quads directory
        return read_quads(quad_path(hord_root, uuid))

    if overlays is None:
        overlays = available

    composed = []
    for ov in overlays:
        if ov in available:
            qpath = quad_path(hord_root, uuid, overlay=ov)
            composed.extend(read_quads(qpath))
    return composed


def find_all_quads_dirs(hord_root: str,
                        overlays: list[str] | None = None) -> list[str]:
    """Return list of quads directories to scan (for incoming link search etc).
    Falls back to legacy .hord/quads/ if no overlays exist."""
    available = list_overlays(hord_root)
    if not available:
        legacy = os.path.join(hord_root, ".hord", "quads")
        return [legacy] if os.path.isdir(legacy) else []

    if overlays is None:
        overlays = available

    dirs = []
    for ov in overlays:
        if ov in available:
            d = os.path.join(hord_root, ".hord", "overlays", ov, "quads")
            if os.path.isdir(d):
                dirs.append(d)
    return dirs
