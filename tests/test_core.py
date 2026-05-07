"""Integration tests for hord CLI core commands."""

import os
import subprocess

import pytest
from click.testing import CliRunner

from hord.cli import cli


class TestInit:
    """Test hord init command."""

    def test_init_creates_skeleton(self, tmp_path):
        """hord init should create .hord/ with expected structure."""
        subprocess.run(["git", "init"], cwd=str(tmp_path), check=True,
                       capture_output=True)

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        assert result.exit_code == 0
        assert os.path.isdir(tmp_path / ".hord")
        assert os.path.isdir(tmp_path / ".hord" / "vocab")
        assert os.path.isdir(tmp_path / ".hord" / "overlays" / "strata" / "quads")
        assert os.path.isdir(tmp_path / ".hord" / "overlays" / "structural" / "quads")
        assert os.path.isfile(tmp_path / ".hord" / "config.toml")
        assert os.path.isfile(tmp_path / ".hord" / "index.tsv")

    def test_init_fails_without_git(self, tmp_path):
        """hord init should fail if not in a git repo."""
        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init"])

        assert result.exit_code != 0
        assert "not inside a git repository" in result.output


class TestNew:
    """Test hord new command."""

    def test_new_card(self, hord_dir, runner):
        """hord new should create a card file with correct structure."""
        os.chdir(str(hord_dir))
        result = runner.invoke(cli, ["new", "Test Concept", "-t", "con"],
                               catch_exceptions=False)

        assert result.exit_code == 0, f"hord new failed: {result.output}"

        # Card should be in content/ directory
        content_dir = hord_dir / "content"
        assert content_dir.is_dir(), "content/ directory not created"

        # Find the created .org file
        org_files = list(content_dir.glob("*.org"))
        assert len(org_files) == 1, f"Expected 1 org file, found {len(org_files)}"

        card_content = org_files[0].read_text()
        assert ":ID:" in card_content
        assert ":TYPE:" in card_content
        assert "wh:con" in card_content
        assert "Test Concept" in card_content


class TestCompile:
    """Test hord compile command."""

    def test_compile_generates_index(self, hord_dir, runner):
        """hord compile should populate index.tsv after creating cards."""
        os.chdir(str(hord_dir))

        # Create a card first
        result = runner.invoke(cli, ["new", "Compile Test", "-t", "con"],
                               catch_exceptions=False)
        assert result.exit_code == 0

        # Compile
        result = runner.invoke(cli, ["compile"], catch_exceptions=False)
        assert result.exit_code == 0

        # Verify index.tsv has content beyond the header
        index_path = hord_dir / ".hord" / "index.tsv"
        lines = index_path.read_text().strip().splitlines()
        assert len(lines) >= 2, f"index.tsv should have header + entries, got: {lines}"


class TestQuery:
    """Test hord query command."""

    def test_query_finds_card(self, hord_dir, runner):
        """hord query should find a compiled card by filename."""
        os.chdir(str(hord_dir))

        # Create and compile a card
        runner.invoke(cli, ["new", "Query Target", "-t", "con"],
                      catch_exceptions=False)
        runner.invoke(cli, ["compile"], catch_exceptions=False)

        # Find the card filename (without extension) from content/
        content_dir = hord_dir / "content"
        org_files = list(content_dir.glob("*.org"))
        assert len(org_files) == 1
        card_stem = org_files[0].stem  # filename without .org

        # Query by filename stem
        result = runner.invoke(cli, ["query", card_stem],
                               catch_exceptions=False)

        assert result.exit_code == 0
        assert "Query Target" in result.output or card_stem in result.output


class TestSearch:
    """Test hord search command."""

    def test_search_finds_match(self, hord_dir, runner):
        """hord search should find a card by title text."""
        os.chdir(str(hord_dir))

        # Create a card with distinctive title and compile
        runner.invoke(cli, ["new", "Xyzzy Plover", "-t", "con"],
                      catch_exceptions=False)
        runner.invoke(cli, ["compile"], catch_exceptions=False)

        # Search for it
        result = runner.invoke(cli, ["search", "Xyzzy"],
                               catch_exceptions=False)

        assert result.exit_code == 0
        assert "Xyzzy" in result.output or "plover" in result.output.lower()


class TestAddBlob:
    """Test hord add command."""

    def test_add_blob_copies_file(self, hord_dir, runner):
        """hord add should copy a file into lib/blob/."""
        os.chdir(str(hord_dir))

        # Create a dummy PDF file
        dummy_pdf = hord_dir / "smith:2020testing.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 fake content")

        # Add it
        result = runner.invoke(
            cli,
            ["add", str(dummy_pdf), "--key", "smith:2020testing",
             "--title", "Testing Things", "--author", "Smith",
             "--year", "2020", "--no-context"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"hord add failed: {result.output}"

        # Verify blob is in lib/blob/
        blob_dir = hord_dir / "lib" / "blob"
        assert blob_dir.is_dir(), "lib/blob/ not created"
        blob_files = list(blob_dir.glob("*.pdf"))
        assert len(blob_files) >= 1, "No PDF found in lib/blob/"


class TestCapture:
    """Test hord capture command."""

    def test_capture_creates_card(self, hord_dir, runner):
        """hord capture should create a card in capture/ directory."""
        os.chdir(str(hord_dir))

        result = runner.invoke(
            cli,
            ["capture", "This is a test thought about integration testing"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"hord capture failed: {result.output}"

        # Verify capture/ directory has a file
        capture_dir = hord_dir / "capture"
        assert capture_dir.is_dir(), "capture/ directory not created"

        org_files = list(capture_dir.glob("*.org"))
        assert len(org_files) == 1, f"Expected 1 capture file, got {len(org_files)}"

        content = org_files[0].read_text()
        assert "integration testing" in content
        assert ":TYPE:" in content
        assert "wh:cap" in content
