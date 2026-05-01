"""Hoard CLI — semantic metadata overlays for git repositories."""

import click

from hord import __version__


@click.group()
@click.version_option(version=__version__, prog_name="hord")
def cli():
    """Hoard: semantic metadata overlays for git repositories.

    Hoard adds a .hord/ directory to any git repo, storing
    structured metadata (quads) alongside your content. Think
    .git/ but for knowledge structure.
    """
    pass


# Import and register subcommands
from hord.init import init_cmd
from hord.compile import compile_cmd
from hord.query import query_cmd
from hord.status import status_cmd
from hord.convert import convert_cmd
from hord.new import new_cmd
from hord.export_html import export_cmd
from hord.tags import tags_cmd
from hord.capture import capture_cmd

cli.add_command(init_cmd, "init")
cli.add_command(compile_cmd, "compile")
cli.add_command(query_cmd, "query")
cli.add_command(status_cmd, "status")
cli.add_command(convert_cmd, "convert")
cli.add_command(new_cmd, "new")
cli.add_command(export_cmd, "export")
cli.add_command(tags_cmd, "tags")
cli.add_command(capture_cmd, "capture")
