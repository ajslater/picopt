"""The doctor's per-path rows: .picopt.yaml lint and timestamps, read-only."""

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from picopt import PROGRAM_NAME, cli
from picopt.config import PicoptConfig
from picopt.config.dirconfig import DirConfig
from picopt.walk.grove import Grove
from tests import IMAGES_DIR
from tests.doctor_util import find_row, isolate_config, run_doctor

__all__ = ()

_SNAPSHOT = f".{PROGRAM_NAME}_treestamps.yaml"
_WAL = f".{PROGRAM_NAME}_treestamps.wal.yaml"
_DIR_CONFIG = ".picopt.yaml"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate_config(monkeypatch, tmp_path)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Build a tree that a real -t -r run has stamped."""
    root = tmp_path / "tree"
    (root / "sub").mkdir(parents=True)
    shutil.copy(IMAGES_DIR / "test_png.png", root)
    shutil.copy(IMAGES_DIR / "test_gif.gif", root / "sub")
    cli.main((PROGRAM_NAME, "-q", "-t", "-r", str(root)))
    assert (root / _SNAPSHOT).is_file()
    return root


def _stamp_state(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        name: ((root / name).read_bytes(), (root / name).stat().st_mtime_ns)
        for name in (_SNAPSHOT, _WAL)
        if (root / name).exists()
    }


def _doctor(
    capsys: pytest.CaptureFixture[str], root: Path, *args: str
) -> tuple[int, str]:
    """Run the doctor on a tree and check it wrote nothing there."""
    before = _stamp_state(root)
    result = run_doctor(capsys, *args, str(root))
    assert _stamp_state(root) == before
    return result


def test_stamps_ok(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _doctor(capsys, tree, "-t", "-r")
    assert code == 0, out
    row = find_row(out, "ok", "stamps")
    assert row is not None
    assert "written" in row
    assert find_row(out, "", "tree root") == f"tree root {tree}"


def test_changed_option_discards(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _doctor(capsys, tree, "-t", "-r", "-c", "WEBP")
    assert code == 0
    row = find_row(out, "WARN", "stamps")
    assert row == (
        "WARN stamps will be discarded: config changed for convert_to; "
        "the run re-optimizes the whole tree"
    )


def test_no_check_config_only_warns(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out = _doctor(capsys, tree, "-t", "-r", "-N", "-c", "WEBP")
    assert find_row(out, "ok", "stamps") is not None
    row = find_row(out, "WARN", "stamps")
    assert row == "WARN stamps config differs for convert_to, but -N skips the check"


def test_sub_dir_config_discards(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tree / "sub" / _DIR_CONFIG).write_text("picopt:\n  convert_to: [WEBP]\n")
    _, out = _doctor(capsys, tree, "-t", "-r")
    row = find_row(out, "WARN", "stamps")
    assert row is not None
    assert "config changed for sub-directory .picopt.yaml contents" in row


def test_corrupt_snapshot(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tree / _SNAPSHOT).write_text("not: [yaml\n")
    code, out = _doctor(capsys, tree, "-t", "-r")
    assert code == 0
    row = find_row(out, "WARN", "stamps")
    assert row is not None
    assert row.startswith("WARN stamps unreadable: ParserError")
    # The parser error is long enough to wrap.
    assert "line 2, column 1; it will be discarded and rewritten" in " ".join(
        out.split()
    )


def test_leftover_wal(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    yaml = YAML(typ="safe")
    config = yaml.load(tree / _SNAPSHOT)["config"]
    with (tree / _WAL).open("w") as wal:
        yaml.dump({"config": config}, wal)
        wal.write("wal:\n- test_png.png: 1700000000.0\n")
    _, out = _doctor(capsys, tree, "-t", "-r")
    row = find_row(out, "", "stamps WAL")
    assert row == (
        "stamps WAL unflushed WAL with 1 entry from an interrupted run; "
        "merged on the next run"
    )


def test_timestamps_off(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out = _doctor(capsys, tree, "-r")
    assert find_row(out, "off", "stamps") == "off stamps timestamps off for this tree"


def test_dir_config_lint(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root_config = tree / _DIR_CONFIG
    root_config.write_text(
        "picopt:\n  convert-to: [CBZ]\n  jobs: 1\n  timestamps: true\n"
    )
    (tree / "sub" / _DIR_CONFIG).write_text("picopt:\n  timestamps: false\n")
    code, out = _doctor(capsys, tree, "-t", "-r")
    assert code == 0
    assert find_row(out, "ok", "root config") == f"ok root config {root_config}"
    rows = [line for line in out.splitlines() if line.lstrip().startswith("WARN")]
    rows = [" ".join(row.split()) for row in rows]
    assert (
        f"WARN unknown key picopt.convert-to ({root_config}): did you mean convert_to?"
        in rows
    )
    assert f"WARN run-scoped key jobs ({root_config}): no per-directory effect" in rows
    sub_config = tree / "sub" / _DIR_CONFIG
    assert (
        f"WARN run-scoped key timestamps ({sub_config}): honoured at a tree root only"
        in rows
    )
    # The root's own timestamps key is honoured, so it isn't flagged.
    assert not any(f"timestamps ({root_config})" in row for row in rows)


def test_tree_settings_diff(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root_config = tree / _DIR_CONFIG
    root_config.write_text("picopt:\n  bigger: true\n")
    _, out = _doctor(capsys, tree, "-r")
    assert find_row(out, "", "bigger") == f"bigger true from {root_config}"


def test_missing_path_fails(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_doctor(capsys, "/nonexistent")
    assert code == 1
    assert find_row(out, "FAIL", "missing") == "FAIL missing does not exist"


def test_symlink_excluded_by_no_symlinks(
    tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    link = tmp_path / "link"
    link.symlink_to(tree)
    code, out = run_doctor(capsys, "-S", str(link))
    assert code == 0
    row = find_row(out, "off", "symlink")
    assert row == "off symlink skipped: -S excludes symlinked targets"


def test_inspect_shares_the_run_config(tree: Path) -> None:
    """Grove.inspect_trees and Grove() build the same grove config."""
    arguments = cli.get_arguments((PROGRAM_NAME, "-q", "-t", "-r", str(tree)))
    picopt_config = PicoptConfig()
    settings = picopt_config.get_config(arguments)
    dirconfig = DirConfig(picopt_config, arguments, settings)
    built = Grove((tree,), dirconfig, settings)._config
    inspected = Grove.grove_config((tree,), dirconfig, settings)
    assert built.paths == inspected.paths
    assert built.tree_config_factory is not None
    assert inspected.tree_config_factory is not None
    assert built.tree_config_factory(tree) == inspected.tree_config_factory(tree)
