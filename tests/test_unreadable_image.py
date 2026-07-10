"""Corrupt-but-identified images warn cleanly instead of dumping tracebacks."""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from tests import get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()


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


def _write_corrupt_bmp(path: Path) -> None:
    """Write a BMP that PIL identifies but rejects: pixel depth 0."""
    header = b"BM" + (54).to_bytes(4, "little") + b"\0" * 4 + (54).to_bytes(4, "little")
    dib = (
        (40).to_bytes(4, "little")  # BITMAPINFOHEADER size
        + (1).to_bytes(4, "little")  # width
        + (1).to_bytes(4, "little")  # height
        + (1).to_bytes(2, "little")  # planes
        + (0).to_bytes(2, "little")  # bpp = 0 -> "Unsupported BMP pixel depth"
        + b"\0" * 24
    )
    path.write_bytes(header + dib)


class TestUnreadableImage:
    """PIL parse failures are expected per-file conditions, not crashes."""

    def test_corrupt_bmp_warns_without_traceback(self, capsys) -> None:
        _write_corrupt_bmp(TMP_ROOT / "corrupt.bmp")

        cli.main((PROGRAM_NAME, "-rvx", "BMP", str(TMP_ROOT)))

        captured = capsys.readouterr()
        assert "unreadable image" in captured.out
        assert "Unsupported BMP pixel depth" in captured.out
        assert "Warnings" in captured.out
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err
        # Degraded to a skip: the corrupt file must survive untouched.
        assert (TMP_ROOT / "corrupt.bmp").is_file()
