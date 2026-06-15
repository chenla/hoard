# Solvay 1927 -- Example Hord

The 1927 Solvay Conference on "Electrons and Photons" brought together
29 of the most distinguished physicists of the twentieth century.
This example hord captures that gathering as a self-contained Hoard
holon demonstration.

## Contents

50 card files organized as:

- 29 person Whole cards (--7.org) -- one for each conference attendee
- 17 expression cards (--solvay-1927.org) -- each person as they were
  in October 1927, not as we remember them today
- 1 event card -- the conference itself
- 1 organization card -- the Solvay Institutes
- 1 media card -- the famous group photograph
- 1 holon definition -- assembles everything into a coherent view

## What This Demonstrates

- **Holons**: A named subset of a hord assembled for a specific
  purpose.  The "Solvay 1927" holon selects 32 cards and presents
  them with expression substitution and type-based ordering.
- **Expression cards**: The same person (Whole) rendered differently
  for a specific context.  Einstein's Whole card covers his full
  life; his expression card shows who he was that day in October 1927.
- **WEMI for cards**: Whole/Expression applied to knowledge cards,
  not just bibliographic records.
- **Temporal context**: Relationships and significance scoped to a
  moment in history -- what Wikipedia flattens away.

## Live Demo

**[Browse online →](https://chenla.github.io/hoard/solvay.html)**

## Local Usage

```
cd examples/solvay-1927
hord compile
hord holon list
hord holon show Solvay_1927--21
hord export --holon Solvay_1927--21
xdg-open _site/holon.html   # Linux (use 'open' on macOS)
```

## Directory Structure

```
solvay-1927/
  .hord/
    config.toml
    vocab/
      terms.tsv
      relations.tsv
  content/          # 50 card files
  lib/
    blob/           # attachments (photograph goes here)
```
