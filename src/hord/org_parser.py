"""Parse org-mode files to extract Hoard metadata.

Handles both old-format records (TYPE: con/concept, inline relations)
and new-format records (TYPE: wh:con, ** Relations section).
"""

import os
import re
from dataclasses import dataclass, field


# Map old-style type codes to vocab term IDs
OLD_TYPE_MAP = {
    "con/concept": "wh:con",
    "concept": "wh:con",
    "pat/pattern": "wh:pat",
    "pattern": "wh:pat",
    "key/keystone": "wh:key",
    "keystone": "wh:key",
    "wrk/work": "wh:wrk",
    "work": "wh:wrk",
    "per/person": "wh:per",
    "person": "wh:per",
    "cat/category": "wh:cat",
    "category": "wh:cat",
    "sys/system": "wh:sys",
    "system": "wh:sys",
    "pla/place": "wh:pla",
    "evt/event": "wh:evt",
    "obj/object": "wh:obj",
    "org/organization": "wh:org",
}

# Map filename suffix to vocab term ID
SUFFIX_TYPE_MAP = {
    "3": "wh:pat",
    "4": "wh:con",
    "5": "wh:key",
    "6": "wh:wrk",
    "7": "wh:per",
    "8": "wh:cat",
    "9": "wh:sys",
    "10": "wh:pla",
    "11": "wh:evt",
    "12": "wh:obj",
    "13": "wh:org",
}

# Regex for org property drawer entries (case-insensitive keys)
PROP_RE = re.compile(r"^\s*:(\w[\w-]*):\s*(.*?)\s*$")

# Regex for org ID links: [[id:UUID][Label]]
ID_LINK_RE = re.compile(r"\[\[id:([0-9a-f-]+)\]\[([^\]]*)\]\]")

# Regex for relation lines: - TT :: ... or - RT :: ...
RELATION_RE = re.compile(
    r"^\s*-\s*(TT|PT|BT|BTG|BTI|BTP|NT|NTG|NTI|NTP|RT|UF|USE|WO|EO|MO|IO)\s*::\s*(.*)",
    re.IGNORECASE,
)

# Regex for ROAM_ALIASES
ROAM_ALIAS_RE = re.compile(r'"([^"]+)"')


@dataclass
class Relation:
    """A thesaurus relationship extracted from an org file."""
    rel_type: str       # TT, BT, NT, RT, UF, USE, PT
    target_uuid: str | None   # UUID of target (None for PT/UF)
    target_label: str   # Display label


@dataclass
class OrgRecord:
    """Parsed metadata from an org-mode word-hord record."""
    uuid: str | None = None
    entity_type: str | None = None  # vocab term ID (e.g. wh:con)
    title: str | None = None
    created: str | None = None
    geo: str | None = None
    filetags: list[str] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    filepath: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.uuid is not None


def type_from_filename(filename: str) -> str | None:
    """Extract type code from filename like 'Concept--8.org'."""
    basename = os.path.splitext(os.path.basename(filename))[0]
    # Match --N at end of filename
    match = re.search(r"--(\d+)$", basename)
    if match:
        return SUFFIX_TYPE_MAP.get(match.group(1))
    # Also try em-dash variant: —N
    match = re.search(r"—(\d+)$", basename)
    if match:
        return SUFFIX_TYPE_MAP.get(match.group(1))
    return None


def parse_org_file(filepath: str) -> OrgRecord:
    """Parse an org-mode file and extract Hoard metadata.

    Handles both old and new format records:
    - Old: :TYPE: con/concept, :Name:, :VER:, inline relations under H1
    - New: :TYPE: wh:con, ** Relations section
    """
    record = OrgRecord(filepath=filepath)

    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")

    # Extract file-level directives
    for line in lines:
        if line.startswith("#+TITLE:"):
            record.title = line.split(":", 1)[1].strip()
        elif line.startswith("#+FILETAGS:"):
            # Parse filetags: "hord" "concept" → ['hord', 'concept']
            record.filetags = re.findall(r'"(\w+)"', line)

    # Extract properties from property drawers
    in_properties = False
    for line in lines:
        stripped = line.strip()
        if stripped == ":PROPERTIES:":
            in_properties = True
            continue
        if stripped == ":END:":
            in_properties = False
            continue
        if in_properties:
            m = PROP_RE.match(line)
            if m:
                key = m.group(1).upper()
                val = m.group(2).strip()
                if key == "ID":
                    record.uuid = val
                elif key == "TYPE":
                    # Normalize old-style types
                    record.entity_type = OLD_TYPE_MAP.get(val, val)
                elif key == "CREATED":
                    record.created = val
                elif key == "GEO":
                    record.geo = val
                elif key == "ROAM_ALIASES":
                    record.aliases = ROAM_ALIAS_RE.findall(val)

    # If no TYPE in properties, try to infer from filename
    if not record.entity_type:
        record.entity_type = type_from_filename(filepath)

    # If still no type, try filetags
    if not record.entity_type and record.filetags:
        for tag in record.filetags:
            tag_lower = tag.lower()
            if tag_lower in OLD_TYPE_MAP:
                record.entity_type = OLD_TYPE_MAP[tag_lower]
                break

    # Extract relations — scan entire file for relation lines
    for line in lines:
        m = RELATION_RE.match(line)
        if m:
            rel_type = m.group(1).upper()
            rest = m.group(2).strip()

            # Check for org ID link
            link_match = ID_LINK_RE.search(rest)
            if link_match:
                record.relations.append(Relation(
                    rel_type=rel_type,
                    target_uuid=link_match.group(1),
                    target_label=link_match.group(2),
                ))
            else:
                # PT or UF without a link — just a label
                record.relations.append(Relation(
                    rel_type=rel_type,
                    target_uuid=None,
                    target_label=rest,
                ))

    return record


def scan_directory(directory: str, recursive: bool = True) -> list[OrgRecord]:
    """Scan a directory for org files and parse each one."""
    records = []
    if recursive:
        for root, dirs, files in os.walk(directory):
            for fname in sorted(files):
                if fname.endswith(".org") and not fname.startswith("#") and not fname.startswith(".#"):
                    fpath = os.path.join(root, fname)
                    record = parse_org_file(fpath)
                    if record.is_valid:
                        records.append(record)
    else:
        for fname in sorted(os.listdir(directory)):
            if fname.endswith(".org") and not fname.startswith("#") and not fname.startswith(".#"):
                fpath = os.path.join(directory, fname)
                record = parse_org_file(fpath)
                if record.is_valid:
                    records.append(record)
    return records
