"""hord init — create .hord/ skeleton in a git repository."""

import os
import shutil

import click

from hord.git_utils import find_git_root
from hord.vocab import default_vocab_path


@click.command("init")
@click.option("--name", default=None, help="Hord name (defaults to directory name)")
def init_cmd(name):
    """Initialize a new .hord/ overlay in the current git repository."""
    git_root = find_git_root(".")
    if git_root is None:
        click.echo("Error: not inside a git repository. Run 'git init' first.", err=True)
        raise SystemExit(1)

    hord_dir = os.path.join(git_root, ".hord")
    if os.path.exists(hord_dir):
        click.echo(f"Error: .hord/ already exists at {hord_dir}", err=True)
        raise SystemExit(1)

    if name is None:
        name = os.path.basename(git_root)

    # Create directory structure
    os.makedirs(os.path.join(hord_dir, "vocab"))
    os.makedirs(os.path.join(hord_dir, "quads"))

    # Write config.toml
    config_path = os.path.join(hord_dir, "config.toml")
    with open(config_path, "w") as f:
        f.write(f'[hord]\nname = "{name}"\nversion = "0.1.0"\n\n')
        f.write('[vocab]\nsource = "local"\n')

    # Write empty index.tsv
    index_path = os.path.join(hord_dir, "index.tsv")
    with open(index_path, "w") as f:
        f.write("path\tuuid\n")

    # Copy default vocabulary
    pkg_vocab = os.path.dirname(default_vocab_path())
    for fname in ["terms.tsv", "relations.tsv"]:
        src = os.path.join(pkg_vocab, fname)
        dst = os.path.join(hord_dir, "vocab", fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            click.echo(f"Warning: default vocab file not found: {src}", err=True)

    click.echo(f"Initialized .hord/ in {git_root}")
    click.echo(f"  name: {name}")
    click.echo(f"  config: {config_path}")
    click.echo(f"  vocab: {os.path.join(hord_dir, 'vocab')}/")
    click.echo(f"  quads: {os.path.join(hord_dir, 'quads')}/")
