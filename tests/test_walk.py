"""Test gif module."""
import shutil

from pathlib import Path

from picopt.settings import Settings
from picopt.stats import ReportStats
from picopt.walk import Walk


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files/")
IMAGES_ROOT = TEST_FILES_ROOT / "images"
TEST_GIF_SRC = IMAGES_ROOT / "test_gif.gif"
TMP_ROOT = Path("/tmp")
OLD_PATH = TMP_ROOT / "old.gif"


def test_comic_archive_skip():
    wob = Walk(Settings())
    path = Path("xxx")
    rep = ReportStats(path)
    res = wob._comic_archive_skip((rep,))
    assert res.final_path == path
