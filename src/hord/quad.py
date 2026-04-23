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


def quad_path(hord_root: str, uuid: str) -> str:
    """Return the filesystem path for a node's quad file.
    Sharded by first 4 chars of UUID."""
    prefix = uuid[:4]
    return os.path.join(hord_root, ".hord", "quads", prefix, f"{uuid}.tsv")
