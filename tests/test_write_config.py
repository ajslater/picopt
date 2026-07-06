"""Test the -w / -W / --write-config-file config writers."""

import os
import stat
import sys
from pathlib import Path

import pytest
from confuse.exceptions import ConfigError
from ruamel.yaml import YAML

from picopt import PROGRAM_NAME, cli
from picopt.config import PicoptConfig, _target_dir_config_paths
from picopt.config.settings import PicoptSettings

__all__ = ()

OWNER_ONLY_MODE = 0o600


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):  # pyright: ignore[reportUnusedFunction]
    """Point confuse at an empty config dir and scrub picopt env vars."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PICOPTDIR", str(tmp_path))


def _get_config(argv: tuple[str, ...]) -> PicoptSettings:
    return PicoptConfig().get_config(cli.get_arguments(argv))


def _load_section(path: Path) -> dict:
    data = YAML().load(path.read_text())
    return dict(data[PROGRAM_NAME])


class TestWriteConfig:
    """-w persists invoked options to the user config."""

    def test_written_config_round_trips(self, tmp_path: Path) -> None:
        _get_config(("picopt", "-w", "-rb", "-x", "CBZ", str(tmp_path)))
        config_path = tmp_path / "config.yaml"
        assert config_path.is_file()
        # The user config dir is PICOPTDIR, so a plain invocation reads it.
        config = _get_config(("picopt", str(tmp_path)))
        assert config.recurse is True
        assert config.bigger is True
        assert "CBZ" in config.formats
        # And explicitly via -C as well.
        config = _get_config(("picopt", "-C", str(config_path), str(tmp_path)))
        assert config.recurse is True

    def test_run_mode_flags_and_paths_not_persisted(self, tmp_path: Path) -> None:
        _get_config(("picopt", "-w", "-rdLq", str(tmp_path)))
        section = _load_section(tmp_path / "config.yaml")
        assert "recurse" in section
        for absent in (
            "dry_run",
            "list_only",
            "verbose",
            "paths",
            "config",
            "write_config",
            "write_dir_config",
            "write_config_file",
        ):
            assert absent not in section

    def test_tuple_options_written_as_lists(self, tmp_path: Path) -> None:
        _get_config(("picopt", "-w", "-x", "CBZ,ZIP", str(tmp_path)))
        section = _load_section(tmp_path / "config.yaml")
        assert sorted(section["extra_formats"]) == ["CBZ", "ZIP"]

    def test_comments_and_unrelated_keys_survive(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("# keep this comment\npicopt:\n  near_lossless: true\n")
        _get_config(("picopt", "-w", "-r", str(tmp_path)))
        text = config_path.read_text()
        assert "# keep this comment" in text
        section = _load_section(config_path)
        assert section["near_lossless"] is True
        assert section["recurse"] is True

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes only")
    def test_written_config_owner_only(self, tmp_path: Path) -> None:
        _get_config(("picopt", "-w", "-r", str(tmp_path)))
        mode = stat.S_IMODE((tmp_path / "config.yaml").stat().st_mode)
        assert mode == OWNER_ONLY_MODE

    def test_invalid_invocation_does_not_write(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            _get_config(("picopt", "-w", "--memory-limit", "banana", str(tmp_path)))
        assert not (tmp_path / "config.yaml").exists()

    def test_write_config_file_explicit_path(self, tmp_path: Path) -> None:
        target = tmp_path / "out" / "myconfig.yaml"
        _get_config(("picopt", "--write-config-file", str(target), "-r", str(tmp_path)))
        assert target.is_file()
        assert _load_section(target)["recurse"] is True


class TestWriteDirConfig:
    """-W writes .picopt.yaml into each target directory."""

    def test_write_dir_config_each_target_dir(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        _get_config(("picopt", "-W", "-b", str(dir_a), str(dir_b)))
        for directory in (dir_a, dir_b):
            section = _load_section(directory / ".picopt.yaml")
            assert section["bigger"] is True

    def test_file_target_writes_parent(self, tmp_path: Path) -> None:
        target_file = tmp_path / "img.png"
        target_file.write_bytes(b"x")
        _get_config(("picopt", "-W", "-b", str(target_file)))
        assert (tmp_path / ".picopt.yaml").is_file()

    def test_updates_existing_dir_config_in_place(self, tmp_path: Path) -> None:
        dir_config = tmp_path / ".picopt.yaml"
        dir_config.write_text("picopt:\n  keep_metadata: false\n")
        _get_config(("picopt", "-W", "-b", str(tmp_path)))
        section = _load_section(dir_config)
        assert section["keep_metadata"] is False
        assert section["bigger"] is True


def test_target_dir_config_paths_dedupes_and_uses_parent(tmp_path: Path) -> None:
    """File targets map to their parent; duplicates collapse."""
    target_file = tmp_path / "img.png"
    target_file.write_bytes(b"x")
    paths = (str(tmp_path), str(target_file), str(tmp_path))
    targets = _target_dir_config_paths(paths)
    assert targets == [tmp_path / ".picopt.yaml"]
