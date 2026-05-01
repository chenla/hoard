"""Parse markdown files with YAML frontmatter to extract Hoard metadata.

Markdown records use YAML frontmatter for structured metadata:

---
id: <uuid>
type: wh:con
title: Record Name
created: 2026-04-22T10:00@Location
license: MIT/CC BY-SA 4.0
relations:
  - TT: <uuid>
  - BT: <uuid>
  - NT: <uuid>
  - RT: <uuid>
aliases:
  - Alternate name
  - 別名
---

# Record Name

Content goes here...
"""

import os
import re
from dataclasses import dataclass, field

from hord.org_parser import OrgRecord, Relation, OLD_TYPE_MAP, SUFFIX_TYPE_MAP


def _parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content.
    Returns (metadata dict, body text).
    Uses simple parsing — no PyYAML dependency."""
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    front = content[4:end]
    body = content[end + 4:]

    meta = {}
    current_key = None
    current_list = None

    for line in front.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List item under a key
        if stripped.startswith("- ") and current_key:
            item = stripped[2:].strip()
            # Strip surrounding quotes
            if (item.startswith('"') and item.endswith('"')) or \
               (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            if current_list is None:
                current_list = []
                meta[current_key] = current_list
            current_list.append(item)
            continue

        # Key: value pair
        if ":" in stripped and not stripped.startswith("-"):
            # Check if this is a top-level key (not indented)
            if not line.startswith(" ") and not line.startswith("\t"):
                parts = stripped.split(":", 1)
                key = parts[0].strip()
                val = parts[1].strip() if len(parts) > 1 else ""
                current_key = key
                if val:
                    meta[key] = val
                    current_list = None
                else:
                    current_list = []
                    meta[key] = current_list

    return meta, body


def _parse_relation_entry(entry: str) -> Relation | None:
    """Parse a relation entry like 'TT: <uuid>' or 'TT: <uuid>  # Label'."""
    if ":" not in entry:
        return None

    parts = entry.split(":", 1)
    rel_type = parts[0].strip().upper()
    rest = parts[1].strip()

    valid_types = {"TT", "PT", "BT", "BTG", "BTI", "BTP",
                   "NT", "NTG", "NTI", "NTP", "RT", "UF", "USE",
                   "WO", "EO", "MO", "IO"}
    if rel_type not in valid_types:
        return None

    # Strip inline comment
    if "#" in rest:
        uuid_part = rest.split("#")[0].strip()
        label = rest.split("#")[1].strip()
    else:
        uuid_part = rest
        label = rest

    # Check if it looks like a UUID
    if re.match(r"^[0-9a-f-]{36}$", uuid_part):
        return Relation(rel_type=rel_type, target_uuid=uuid_part, target_label=label)
    else:
        return Relation(rel_type=rel_type, target_uuid=None, target_label=uuid_part)


def type_from_filename(filename: str) -> str | None:
    """Extract type code from filename like 'Concept--8.md'."""
    basename = os.path.splitext(os.path.basename(filename))[0]
    match = re.search(r"--(\d+)$", basename)
    if match:
        return SUFFIX_TYPE_MAP.get(match.group(1))
    return None


def parse_md_file(filepath: str) -> OrgRecord:
    """Parse a markdown file with YAML frontmatter and extract Hoard metadata.
    Returns an OrgRecord for compatibility with the compile pipeline."""
    record = OrgRecord(filepath=filepath)

    with open(filepath, "r") as f:
        content = f.read()

    meta, body = _parse_yaml_frontmatter(content)

    # Extract fields
    record.uuid = meta.get("id")
    record.title = meta.get("title")
    record.created = meta.get("created")
    record.geo = meta.get("geo")

    # Type
    raw_type = meta.get("type", "")
    record.entity_type = OLD_TYPE_MAP.get(raw_type, raw_type) if raw_type else None
    if not record.entity_type:
        record.entity_type = type_from_filename(filepath)

    # Tags
    tags = meta.get("tags")
    if isinstance(tags, list):
        record.tags = tags
        record.filetags = tags  # backwards compat for type inference
    elif isinstance(tags, str):
        record.tags = [t.strip() for t in tags.split(",")]
        record.filetags = record.tags

    # Relations
    relations = meta.get("relations")
    if isinstance(relations, list):
        for entry in relations:
            rel = _parse_relation_entry(entry)
            if rel:
                record.relations.append(rel)

    # Aliases
    aliases = meta.get("aliases")
    if isinstance(aliases, list):
        record.aliases = aliases

    return record


def scan_directory(directory: str, recursive: bool = True) -> list[OrgRecord]:
    """Scan a directory for markdown files and parse each one."""
    records = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            for fname in sorted(files):
                if fname.endswith(".md") and not fname.startswith("."):
                    fpath = os.path.join(root, fname)
                    record = parse_md_file(fpath)
                    if record.is_valid:
                        records.append(record)
    else:
        for fname in sorted(os.listdir(directory)):
            if fname.endswith(".md") and not fname.startswith("."):
                fpath = os.path.join(directory, fname)
                record = parse_md_file(fpath)
                if record.is_valid:
                    records.append(record)
    return records
