"""Shared fixtures for hord integration tests."""

import os
import subprocess

import pytest
from click.testing import CliRunner

from hord.cli import cli


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def hord_dir(tmp_path):
    """Create a temp directory with git init + hord init already done.

    Returns the path to the initialized hord root.
    """
    # git init is required before hord init
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True,
                   capture_output=True)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"hord init failed: {result.output}"

    return tmp_path
