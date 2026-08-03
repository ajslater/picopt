"""Per-tree timestamps resolved from tree-root .picopt.yaml files."""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_FN = "test_png.png"
TIMESTAMPS_FN = f".{PROGRAM_NAME}_treestamps.yaml"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Scrub env, isolate the user config, and build a fresh tree."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PICOPTDIR", str(tmp_path))
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True)
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def _write_dir_config(directory: Path, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".picopt.yaml").write_text(text)


class TestTreeRootTimestamps:
    """The tree root's .picopt.yaml governs that tree's timestamps."""

    def test_flag_run_stamps_honored_by_yaml_run(self, capsys) -> None:
        """Identical effective options via CLI flags or root yaml must match."""
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)

        cli.main((PROGRAM_NAME, "-rtvx", "PNG", str(TMP_ROOT)))
        optimized_mtime = (TMP_ROOT / PNG_FN).stat().st_mtime_ns

        # Express the same effective config in the tree root's yaml and
        # run without any of those CLI flags.
        _write_dir_config(
            TMP_ROOT,
            "picopt:\n  recurse: true\n  timestamps: true\n  extra_formats: [PNG]\n",
        )
        capsys.readouterr()
        cli.main((PROGRAM_NAME, "-v", str(TMP_ROOT)))

        out = capsys.readouterr().out
        assert "config mismatch" not in out
        assert (TMP_ROOT / PNG_FN).stat().st_mtime_ns == optimized_mtime

    def test_root_yaml_timestamps_true_activates_without_flag(self) -> None:
        """timestamps: true in the tree root's yaml stamps without -t."""
        _write_dir_config(TMP_ROOT, "picopt:\n  recurse: true\n  timestamps: true\n")
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)
        argv = (PROGRAM_NAME, "-vx", "PNG", str(TMP_ROOT))

        cli.main(argv)
        assert (TMP_ROOT / TIMESTAMPS_FN).is_file()
        optimized_mtime = (TMP_ROOT / PNG_FN).stat().st_mtime_ns

        cli.main(argv)
        assert (TMP_ROOT / PNG_FN).stat().st_mtime_ns == optimized_mtime

    def test_root_yaml_comment_edit_keeps_stamps(self) -> None:
        """Only option values invalidate the root config, not file bytes."""
        yaml_body = "picopt:\n  recurse: true\n  timestamps: true\n  bigger: false\n"
        _write_dir_config(TMP_ROOT, yaml_body)
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)
        argv = (PROGRAM_NAME, "-vx", "PNG", str(TMP_ROOT))

        cli.main(argv)
        optimized_mtime = (TMP_ROOT / PNG_FN).stat().st_mtime_ns

        # Byte churn, identical values: stamps must hold.
        _write_dir_config(TMP_ROOT, f"# a comment\n{yaml_body}")
        cli.main(argv)
        assert (TMP_ROOT / PNG_FN).stat().st_mtime_ns == optimized_mtime

        # A value change must invalidate: with bigger=true the re-optimized
        # (equal or larger) result is kept, so the mtime changes.
        _write_dir_config(TMP_ROOT, yaml_body.replace("bigger: false", "bigger: true"))
        cli.main(argv)
        assert (TMP_ROOT / PNG_FN).stat().st_mtime_ns != optimized_mtime

    def test_subdir_yaml_comment_edit_keeps_stamps(self) -> None:
        """The fingerprint hashes subdir config values, not file bytes."""
        photos = TMP_ROOT / "photos"
        yaml_body = "picopt:\n  bigger: false\n"
        _write_dir_config(photos, yaml_body)
        shutil.copy(IMAGES_DIR / PNG_FN, photos / PNG_FN)
        argv = (PROGRAM_NAME, "-rtvx", "PNG", str(TMP_ROOT))

        cli.main(argv)
        optimized_mtime = (photos / PNG_FN).stat().st_mtime_ns

        # Byte churn, identical values: stamps must hold.
        _write_dir_config(photos, f"# a comment\n{yaml_body}")
        cli.main(argv)
        assert (photos / PNG_FN).stat().st_mtime_ns == optimized_mtime

        # A value change must flip the fingerprint and re-process the tree.
        _write_dir_config(photos, "picopt:\n  bigger: true\n")
        cli.main(argv)
        assert (photos / PNG_FN).stat().st_mtime_ns != optimized_mtime

    def test_multi_top_path_then_single_path_keeps_stamps(self, capsys) -> None:
        """Each tree's fingerprint sees only its own configs."""
        tree_a = TMP_ROOT / "a"
        tree_b = TMP_ROOT / "b"
        tree_a.mkdir()
        # A config below b would have poisoned the old all-paths digest.
        _write_dir_config(tree_b / "sub", "picopt:\n  bigger: false\n")
        shutil.copy(IMAGES_DIR / PNG_FN, tree_a / PNG_FN)
        shutil.copy(IMAGES_DIR / PNG_FN, tree_b / "sub" / PNG_FN)

        cli.main((PROGRAM_NAME, "-rtvx", "PNG", str(tree_a), str(tree_b)))
        optimized_mtime = (tree_a / PNG_FN).stat().st_mtime_ns

        capsys.readouterr()
        cli.main((PROGRAM_NAME, "-rtvx", "PNG", str(tree_a)))

        out = capsys.readouterr().out
        assert "config mismatch" not in out
        assert (tree_a / PNG_FN).stat().st_mtime_ns == optimized_mtime

    def test_config_mismatch_warning_visible(self, capsys) -> None:
        """Discarding stamps on config change warns with the differing key."""
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)

        cli.main((PROGRAM_NAME, "-rtvx", "PNG", str(TMP_ROOT)))

        capsys.readouterr()
        # Flip one recorded option: bigger.
        cli.main((PROGRAM_NAME, "-rtbvx", "PNG", str(TMP_ROOT)))

        out = capsys.readouterr().out
        assert "config mismatch" in out
        assert "bigger" in out

    def test_config_mismatch_rewritten_when_nothing_optimized(self, capsys) -> None:
        """A discarded timestamps file is rewritten by a run that optimizes nothing."""
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)
        cli.main((PROGRAM_NAME, "-rtvx", "PNG", str(TMP_ROOT)))

        # Without any optimizable file the mismatch run sets no file timestamps.
        (TMP_ROOT / PNG_FN).unlink()
        capsys.readouterr()
        argv = (PROGRAM_NAME, "-rtbvx", "PNG", str(TMP_ROOT))
        cli.main(argv)
        assert "config mismatch" in capsys.readouterr().out

        # The timestamps file now records the current config...
        stamps = YAML(typ="safe").load(TMP_ROOT / TIMESTAMPS_FN)
        assert stamps["config"]["bigger"] is True

        # ...so the same run again loads it without warning.
        cli.main(argv)
        assert "config mismatch" not in capsys.readouterr().out
