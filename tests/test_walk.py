"""Test gif module."""
import shutil

from pathlib import Path

from picopt.settings import Settings
from picopt.stats import ReportStats
from picopt.walk import Walk
from tests import COMIC_DIR
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TEST_CBR_SRC = COMIC_DIR / "test_cbr.cbr"
TEST_GIF_SRC = IMAGES_DIR / "test_gif.gif"
TMP_ROOT = get_test_dir()
OLD_PATH = TMP_ROOT / "old.gif"


def _teardown():
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_comic_archive_skip():
    wob = Walk(Settings())
    path = Path("xxx")
    rep = ReportStats(path)
    res = wob._comic_archive_skip((rep,))
    assert res.final_path == path


def test_walk_comic_archive_skip():
    _teardown()
    TMP_ROOT.mkdir()
    cbr = TMP_ROOT / "test.cbr"
    # cbz = TMP_ROOT / "test.cbz"
    shutil.copy(TEST_CBR_SRC, cbr)
    # old_size = cbr.stat().st_size
    settings = Settings()
    wob = Walk(settings)
    result_set = wob.walk_comic_archive(cbr, "CBR", None)
    res = result_set.pop()
    rep = res.get()
    assert not rep.error
    assert rep.final_path == cbr
    assert rep.bytes_in == 0
    assert rep.bytes_out == 0
    wob._pool.close()
    wob._pool.join()
    _teardown()


def test_walk_comic_archive_bigger():
    _teardown()
    TMP_ROOT.mkdir()
    cbr = TMP_ROOT / "test.cbr"
    cbz = TMP_ROOT / "test.cbz"
    shutil.copy(TEST_CBR_SRC, cbr)
    old_size = cbr.stat().st_size
    settings = Settings()
    settings.comics = True
    settings.bigger = True
    wob = Walk(settings)
    result_set = wob.walk_comic_archive(cbr, "CBR", None)
    res = result_set.pop()
    rep = res.get()
    assert not rep.error
    assert rep.final_path == cbz
    assert rep.bytes_in == old_size
    assert rep.bytes_out > 0
    wob._pool.close()
    wob._pool.join()
    _teardown()
