# Contributing to Hoard

## Development setup

```bash
git clone https://github.com/chenla/hoard
cd hoard
pip install -e ".[dev]"
```

This installs the package in editable mode with test dependencies.

## Running tests

```bash
pytest tests/ -v
```

Tests use temporary directories — no external services or credentials needed.

## Project structure

```
src/hord/
├── cli.py              # Click entry point
├── compile.py          # org/markdown → quads
├── query.py            # Entity lookup
├── new.py              # Card creation
├── search.py           # Full-text search
├── link.py             # Thesaurus relations
├── add.py              # Blob store management
├── capture.py          # Quick-capture
├── import_cards.py     # Multi-format importer
├── export_html.py      # Static site generation
├── mobile.py           # HTTP capture server
├── web.py              # Local web UI
├── persona.py          # Role-specific overlays
├── mcp_server.py       # MCP tool server
├── org_parser.py       # Org-mode parser
├── md_parser.py        # Markdown parser
├── quad.py             # Quad read/write
├── vocab.py            # Vocabulary management
└── git_utils.py        # Git helpers
```

## Making changes

1. Create a branch: `git checkout -b my-change`
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Commit with a clear message describing what and why
5. Open a pull request against `main`

## Commit messages

Use present tense, imperative mood. Focus on why, not what.

```
Add blob deduplication by content hash

Previously, adding the same PDF twice created duplicates in
lib/blob/. Now checks SHA-256 before copying.
```

## What to work on

Check [open issues](https://github.com/chenla/hoard/issues) or
propose something new via a feature request issue.

Areas that especially welcome help:
- **Tests** — more coverage, edge cases, parser tests
- **Import formats** — additional source formats (Bear, Apple Notes, etc.)
- **Documentation** — tutorials, examples, corrections

## Code style

- Python 3.10+ (use type hints where helpful, not religiously)
- No linter enforced yet — just be consistent with surrounding code
- Prefer clarity over cleverness

## License

By contributing, you agree that your contributions will be licensed
under MIT (code) and CC BY 4.0 (documentation).
