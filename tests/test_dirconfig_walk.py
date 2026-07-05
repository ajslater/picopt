"""End-to-end tests for per-directory .picopt.yaml in the walk."""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from zipfile import ZipFile

import pytest

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_FN = "test_png.png"
CBR_FN = "test_cbr.cbr"
CBZ_FN = "test_cbz.cbz"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path) -> Iterator[None]:
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


class TestDirConfigWalk:
    """Directory configs steer the walk, handlers, and conversions."""

    def test_convert_to_applies_only_in_configured_subtree(self) -> None:
        comics = TMP_ROOT / "comics"
        _write_dir_config(comics, "picopt:\n  convert_to: [CBZ]\n")
        shutil.copy(CONTAINER_DIR / CBR_FN, comics / CBR_FN)
        shutil.copy(CONTAINER_DIR / CBR_FN, TMP_ROOT / CBR_FN)

        cli.main((PROGRAM_NAME, "-rvx", "CBR,CBZ", str(TMP_ROOT)))

        # Converted under comics/ ...
        assert (comics / "test_cbr.cbz").is_file()
        assert not (comics / CBR_FN).exists()
        # ... untouched at the root (no convert target there).
        assert (TMP_ROOT / CBR_FN).is_file()

    def test_recurse_false_subtree_untouched(self, tmp_path: Path) -> None:
        # recurse comes from the user config so the dir config can override
        # it — an explicit CLI -r would (correctly) win over both.
        (tmp_path / "config.yaml").write_text("picopt:\n  recurse: true\n")
        frozen = TMP_ROOT / "frozen"
        _write_dir_config(frozen, "picopt:\n  recurse: false\n")
        shutil.copy(IMAGES_DIR / PNG_FN, frozen / PNG_FN)
        shutil.copy(IMAGES_DIR / PNG_FN, TMP_ROOT / PNG_FN)
        frozen_size = (frozen / PNG_FN).stat().st_size

        cli.main((PROGRAM_NAME, "-vx", "PNG", str(TMP_ROOT)))

        assert (frozen / PNG_FN).stat().st_size == frozen_size
        assert (TMP_ROOT / PNG_FN).stat().st_size < frozen_size

    def test_cli_recurse_beats_dir_config(self) -> None:
        frozen = TMP_ROOT / "frozen"
        _write_dir_config(frozen, "picopt:\n  recurse: false\n")
        shutil.copy(IMAGES_DIR / PNG_FN, frozen / PNG_FN)
        orig_size = (frozen / PNG_FN).stat().st_size

        cli.main((PROGRAM_NAME, "-rvx", "PNG", str(TMP_ROOT)))

        assert (frozen / PNG_FN).stat().st_size < orig_size

    def test_per_dir_ignore(self) -> None:
        photos = TMP_ROOT / "photos"
        _write_dir_config(photos, "picopt:\n  ignore: ['*skipme*']\n")
        shutil.copy(IMAGES_DIR / PNG_FN, photos / "skipme.png")
        shutil.copy(IMAGES_DIR / PNG_FN, photos / "doit.png")
        orig_size = (photos / "skipme.png").stat().st_size

        cli.main((PROGRAM_NAME, "-rvx", "PNG", str(TMP_ROOT)))

        assert (photos / "skipme.png").stat().st_size == orig_size
        assert (photos / "doit.png").stat().st_size < orig_size

    def test_dir_config_edit_invalidates_timestamps(self) -> None:
        photos = TMP_ROOT / "photos"
        _write_dir_config(photos, "picopt:\n  bigger: false\n")
        shutil.copy(IMAGES_DIR / PNG_FN, photos / PNG_FN)
        argv = (PROGRAM_NAME, "-rtvx", "PNG", str(TMP_ROOT))

        cli.main(argv)
        optimized_mtime = (photos / PNG_FN).stat().st_mtime_ns

        # Second run: stamped, untouched.
        cli.main(argv)
        assert (photos / PNG_FN).stat().st_mtime_ns == optimized_mtime

        # Edit the directory config: the fingerprint flips and the tree
        # re-processes (the already-optimized file is re-examined; its
        # replacement attempt is discarded but it is no longer skipped
        # by timestamp, so it gets a fresh stamp pass).
        _write_dir_config(photos, "picopt:\n  bigger: true\n")
        cli.main(argv)
        # With bigger=true the re-optimized (equal or larger) result is
        # kept, so the file's mtime changes — proof it was re-processed.
        assert (photos / PNG_FN).stat().st_mtime_ns != optimized_mtime

    def test_formats_banner_prints_once_with_write_dir_config(self, capsys) -> None:
        # -W plants a .picopt.yaml at the target root, so every directory
        # re-resolves settings and finds it in its ancestry — skipping the
        # "no dir config -> reuse run-wide settings" fast path and rebuilding
        # the config once per directory. The run-wide "Optimizing formats"
        # banner must still be emitted exactly once, not per directory.
        for sub in ("", "a", "a/b", "c"):
            directory = TMP_ROOT / sub if sub else TMP_ROOT
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copy(IMAGES_DIR / PNG_FN, directory / PNG_FN)

        cli.main((PROGRAM_NAME, "-rvx", "PNG", str(TMP_ROOT), "-W"))

        out = capsys.readouterr().out
        assert out.count("Optimizing formats") == 1

    def test_archive_members_inherit_dir_config(self) -> None:
        comics = TMP_ROOT / "comics"
        _write_dir_config(comics, "picopt:\n  convert_to: [WEBP]\n")
        comics_cbz = comics / "pngs.cbz"
        root_cbz = TMP_ROOT / "pngs.cbz"
        # A CBZ with a losslessly-convertible (PNG) member.
        with ZipFile(comics_cbz, "w") as zf:
            zf.write(IMAGES_DIR / PNG_FN, PNG_FN)
        shutil.copy(comics_cbz, root_cbz)

        cli.main((PROGRAM_NAME, "-rvx", "CBZ,PNG,WEBP", str(TMP_ROOT)))

        with ZipFile(comics_cbz) as zf:
            comics_suffixes = {Path(n).suffix for n in zf.namelist()}
        with ZipFile(root_cbz) as zf:
            root_suffixes = {Path(n).suffix for n in zf.namelist()}
        # Members under comics/ converted to webp; the root archive kept
        # its original member formats.
        assert comics_suffixes == {".webp"}
        assert root_suffixes == {".png"}
