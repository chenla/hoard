"""Git utilities for Hoard — blob hashing and repo detection."""

import os
import subprocess


def find_git_root(path: str = ".") -> str | None:
    """Walk up from path to find the nearest .git/ directory.
    Returns the repo root or None."""
    path = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def find_hord_root(path: str = ".") -> str | None:
    """Walk up from path to find the nearest .hord/ directory.
    Returns the repo root or None."""
    path = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(path, ".hord")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def read_config(hord_root: str) -> dict:
    """Read .hord/config.toml and return a flat dict of settings.
    Handles basic TOML parsing (key = "value" pairs)."""
    config = {}
    config_path = os.path.join(hord_root, ".hord", "config.toml")
    if not os.path.exists(config_path):
        return config
    import re
    with open(config_path, "r") as f:
        for line in f:
            m = re.match(r'^(\w+)\s*=\s*"(.+)"', line.strip())
            if m:
                config[m.group(1)] = m.group(2)
    return config


def blob_hash(filepath: str) -> str:
    """Compute the git blob hash for a file without requiring
    it to be in a git repo. Uses git hash-object."""
    result = subprocess.run(
        ["git", "hash-object", filepath],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def blob_hash_at_head(filepath: str, git_root: str) -> str | None:
    """Get the blob hash for a file at HEAD.
    Returns None if the file isn't tracked."""
    relpath = os.path.relpath(filepath, git_root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"HEAD:{relpath}"],
            capture_output=True, text=True, check=True,
            cwd=git_root,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None
