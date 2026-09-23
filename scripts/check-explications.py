#!/usr/bin/env python3
"""Check that every facet-value explication uses only NSM primes.

    python3 scripts/check-explications.py            # report
    python3 scripts/check-explications.py --words    # also list the vocabulary

WHY THIS EXISTS.  Hoard's facets are enumerated option sets -- :STATUS: is
five values, :PRESERVATION: is four -- and an option set is only as stable as
the words in its labels.  Left as ordinary English prose, "reconstructible"
means whatever the reader's decade thinks it means, and a facet that drifts
takes every holon tagged with it along.

So each value carries an explication written in Natural Semantic Metalanguage:
the ~65 meanings that cannot be defined without circularity and that turn up
as words in every language examined.  A definition built only from those
cannot go in a circle, and can be re-entered by someone with no access to the
tradition that wrote it.

The check is mechanical, which is the point.  A word that FEELS primitive and
is not -- "must", "change", "machine", "lost" -- is exactly what slips past a
careful writer, and exactly what this catches.

Exit code 1 if any explication uses a word that is neither a prime nor one of
the declared grammatical words.  See
ybr/ww-s/scaffolds/natural-semantic-metalanguage--card.org
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VOCAB = os.path.join(HERE, "..", "vocab")


def load_primes(path):
    """primes, grammar, and inflected forms.  A prime is a MEANING; its
    exponent inflects normally.  'someone said' is SAY, not a violation --
    the first run of this checker flagged twelve of those and was wrong."""
    primes, grammar = set(), set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            kind, word = parts[0].strip(), parts[1].strip().lower()
            if kind == "prime":
                primes.add(word)
            elif kind == "form":
                primes.add(word)          # an inflection of a prime is a prime
            else:
                grammar.add(word)
    return primes, grammar


def load_explications(path):
    """Facet VALUES only.  A facet header's note is documentation, not a
    definition, and is exempt -- it is allowed to say 'Values are f:st-*'."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("id\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 3 or not parts[0].startswith("f:"):
                continue
            if parts[2].startswith("Facet:"):
                continue
            out.append((parts[0], parts[1], parts[2]))
    return out


def words(text):
    # '/' separates clauses; NSM has no punctuation of its own
    return [w for w in re.findall(r"[a-z']+", text.lower()) if w]


def main(argv):
    primes, grammar = load_primes(os.path.join(VOCAB, "nsm-primes.tsv"))
    allowed = primes | grammar
    rows = load_explications(os.path.join(VOCAB, "terms.tsv"))

    if "--words" in argv:
        print("  primes  %d\n  grammar %d" % (len(primes), len(grammar)))

    bad = 0
    for tid, label, note in rows:
        offenders = [w for w in words(note) if w not in allowed]
        if offenders:
            bad += 1
            seen, uniq = set(), []
            for w in offenders:
                if w not in seen:
                    seen.add(w); uniq.append(w)
            print("  FAIL  %-24s %s" % (label, ", ".join(uniq)))
    print()
    print("  %d explications checked, %d clean, %d with words outside the set"
          % (len(rows), len(rows) - bad, bad))
    if bad:
        print("  -> either rewrite the explication, or declare the word in "
              "vocab/nsm-primes.tsv and say why")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
