"""Test per-directory .picopt.yaml resolution."""

import os
from pathlib import Path

import pytest

from picopt import cli
from picopt.config import PicoptConfig
from picopt.config.dirconfig import DirConfig
from picopt.log.summary import Stats

__all__ = ()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    """Point confuse at an empty config dir and scrub picopt env vars."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    config_dir = tmp_path / "confuse-config"
    config_dir.mkdir()
    monkeypatch.setenv("PICOPTDIR", str(config_dir))


def _dc(target: Path, *argv: str) -> tuple[DirConfig, Stats]:
    """Build a DirConfig the way Walk does."""
    args = cli.get_arguments(("picopt", *argv, str(target)))
    picopt_config = PicoptConfig()
    global_settings = picopt_config.get_config(args)
    stats = Stats()
    return DirConfig(PicoptConfig(), args, global_settings, stats), stats


def _write(directory: Path, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    config_file = directory / ".picopt.yaml"
    config_file.write_text(text)
    return config_file


class TestDirConfig:
    """Per-directory resolution semantics."""

    def test_no_config_returns_global_instance(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        media.mkdir()
        dirconfig, _ = _dc(media)
        settings = dirconfig.get_settings(media, media)
        assert settings is dirconfig._global_settings

    def test_directory_config_overrides_default(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  bigger: true\n")
        dirconfig, _ = _dc(media)
        assert dirconfig._global_settings.bigger is False
        assert dirconfig.get_settings(media, media).bigger is True

    def test_deeper_directory_wins(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        deep = media / "deep"
        _write(media, "picopt:\n  near_lossless: true\n")
        _write(deep, "picopt:\n  near_lossless: false\n")
        dirconfig, _ = _dc(media)
        assert dirconfig.get_settings(media, media).near_lossless is True
        assert dirconfig.get_settings(media, deep).near_lossless is False

    def test_boundary_stops_at_top_path(self, tmp_path: Path) -> None:
        _write(tmp_path, "picopt:\n  bigger: true\n")
        media = tmp_path / "media"
        media.mkdir()
        dirconfig, _ = _dc(media)
        settings = dirconfig.get_settings(media, media)
        assert settings.bigger is False

    def test_cli_wins_over_directory_config(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  keep_metadata: true\n")
        dirconfig, _ = _dc(media, "-M")
        assert dirconfig.get_settings(media, media).keep_metadata is False

    def test_env_wins_over_directory_config(self, tmp_path: Path, monkeypatch) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  bigger: false\n")
        monkeypatch.setenv("PICOPT_PICOPT__BIGGER", "True")
        dirconfig, _ = _dc(media)
        assert dirconfig.get_settings(media, media).bigger is True

    def test_formats_replace_not_union(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  formats: [CBZ]\n")
        dirconfig, _ = _dc(media)
        settings = dirconfig.get_settings(media, media)
        assert settings.formats == ("CBZ",)

    def test_full_schema_convert_to(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  convert_to: [WEBP]\n")
        dirconfig, _ = _dc(media)
        settings = dirconfig.get_settings(media, media)
        assert settings.convert_to is not None
        assert "WEBP" in settings.convert_to

    def test_single_file_target_boundary(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  bigger: true\n")
        _write(tmp_path, "picopt:\n  near_lossless: true\n")
        target_file = media / "img.png"
        target_file.write_bytes(b"x")
        dirconfig, _ = _dc(target_file)
        settings = dirconfig.get_settings(media, media)
        assert settings.bigger is True
        # The config above the target boundary must not apply.
        assert settings.near_lossless is False

    def test_malformed_config_falls_back_and_records_error(
        self, tmp_path: Path
    ) -> None:
        media = tmp_path / "media"
        _write(media / "bad", "picopt: [not: a: mapping\n")
        _write(media / "good", "picopt:\n  bigger: true\n")
        dirconfig, stats = _dc(media)
        bad_settings = dirconfig.get_settings(media, media / "bad")
        assert bad_settings is dirconfig._global_settings
        assert stats.errors
        # A sibling with a valid config still resolves.
        assert dirconfig.get_settings(media, media / "good").bigger is True

    def test_malformed_config_logged_once(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt: [not: a: mapping\n")
        child_a = media / "a"
        child_b = media / "b"
        child_a.mkdir()
        child_b.mkdir()
        dirconfig, stats = _dc(media)
        dirconfig.get_settings(media, child_a)
        dirconfig.get_settings(media, child_b)
        assert len(stats.errors) == 1

    def test_settings_cached_per_directory(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(media, "picopt:\n  bigger: true\n")
        dirconfig, _ = _dc(media)
        first = dirconfig.get_settings(media, media)
        second = dirconfig.get_settings(media, media)
        assert first is second

    def test_run_mode_keys_forced_run_level(self, tmp_path: Path) -> None:
        media = tmp_path / "media"
        _write(
            media,
            "picopt:\n  dry_run: true\n  list_only: true\n  timestamps: true\n"
            "  bigger: true\n",
        )
        dirconfig, _ = _dc(media)
        settings = dirconfig.get_settings(media, media)
        # The per-directory value applies for normal keys...
        assert settings.bigger is True
        # ...but run-mode keys stay pinned to the run-level values.
        assert settings.dry_run is False
        assert settings.list_only is False
        assert settings.timestamps is False
