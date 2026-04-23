"""Vocabulary management — load, lookup, and validate terms."""

import os
from dataclasses import dataclass


@dataclass
class Term:
    id: str
    label: str
    scope_note: str


class Vocabulary:
    """A loaded vocabulary from terms.tsv."""

    def __init__(self, terms: dict[str, Term]):
        self._terms = terms

    @classmethod
    def load(cls, terms_path: str) -> "Vocabulary":
        """Load vocabulary from a terms.tsv file."""
        terms = {}
        with open(terms_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("id\t"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    terms[parts[0]] = Term(
                        id=parts[0], label=parts[1], scope_note=parts[2]
                    )
                elif len(parts) == 2:
                    terms[parts[0]] = Term(
                        id=parts[0], label=parts[1], scope_note=""
                    )
        return cls(terms)

    def lookup(self, term_id: str) -> Term | None:
        return self._terms.get(term_id)

    def label(self, term_id: str) -> str:
        """Return the human-readable label for a term ID,
        or the raw ID if not found."""
        t = self._terms.get(term_id)
        return t.label if t else term_id

    def is_valid(self, term_id: str) -> bool:
        return term_id in self._terms

    def all_terms(self) -> list[Term]:
        return list(self._terms.values())


def find_vocab(hord_root: str) -> str | None:
    """Find terms.tsv in a hord's .hord/vocab/ directory."""
    path = os.path.join(hord_root, ".hord", "vocab", "terms.tsv")
    if os.path.exists(path):
        return path
    return None


def default_vocab_path() -> str:
    """Return the path to the default vocabulary shipped with the package."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))),
        "vocab", "terms.tsv"
    )
