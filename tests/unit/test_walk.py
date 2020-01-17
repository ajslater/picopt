"""Test gif module."""
import shutil

from argparse import Namespace

from picopt.settings import Settings
from picopt.stats import ReportStats
from picopt.timestamp import RECORD_FILENAME
from picopt.walk import Walk
from tests import COMIC_DIR
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()  # hides module from pydocstring
TEST_CBR_SRC = COMIC_DIR / "test_cbr.cbr"
TEST_GIF_SRC = IMAGES_DIR / "test_gif.gif"
TEST_JPG_SRC = IMAGES_DIR / "test_jpg.jpg"
TMP_ROOT = get_test_dir()
OLD_PATH = TMP_ROOT / "old.gif"


def _teardown():
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_comic_archive_skip() -> None:
    wob = Walk(Settings())
    path = TMP_ROOT / "xxx"
    rep = ReportStats(path)
    res = wob._comic_archive_skip((rep,))
    assert res.final_path == path
    _teardown()


def test_walk_comic_archive_skip() -> None:
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


def test_walk_comic_archive_bigger() -> None:
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


def test_is_skippable_unset() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.touch()
    settings = Settings()
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert not res
    _teardown()


def test_is_skippable_symlink() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.symlink_to(TMP_ROOT)
    settings = Settings()
    settings.follow_symlinks = False
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert res
    _teardown()


def test_is_skippable_symlink_quiet() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.symlink_to(TMP_ROOT)
    settings = Settings()
    settings.follow_symlinks = False
    settings.verbose = 0
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert res
    _teardown()


def test_is_skippable_timestamp() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / RECORD_FILENAME
    path.touch()
    settings = Settings()
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert res
    _teardown()


def test_is_skippable_dne() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    settings = Settings()
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert res
    _teardown()


def test_is_skippable_quiet() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    settings = Settings()
    settings.verbose = 0
    wob = Walk(settings)
    res = wob._is_skippable(path)
    assert res
    _teardown()


def test_is_older_than_timestamp_none() -> None:
    res = Walk._is_older_than_timestamp(TMP_ROOT, None, None)
    assert not res
    _teardown()


def test_is_older_than_timestamp_older() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.touch()
    walk_after = path.stat().st_mtime + 100
    res = Walk._is_older_than_timestamp(path, walk_after, None)
    assert res
    _teardown()


def test_is_older_than_timestamp_same() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.touch()
    walk_after = path.stat().st_mtime
    res = Walk._is_older_than_timestamp(path, walk_after, None)
    assert res
    _teardown()


def test_is_older_than_timestamp_newer() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.touch()
    walk_after = path.stat().st_mtime - 100
    res = Walk._is_older_than_timestamp(path, walk_after, None)
    assert not res
    _teardown()


def test_is_older_than_timestamp_older_archive() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.txt"
    path.touch()
    walk_after = path.stat().st_mtime - 100
    archive_mtime = walk_after + 200
    res = Walk._is_older_than_timestamp(path, walk_after, archive_mtime)
    assert not res
    _teardown()


def test_walk_file_older_than() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "text.txt"
    path.touch()
    walk_after = path.stat().st_mtime
    wos = Walk(Settings())
    res = wos.walk_file(path, walk_after)
    assert len(res) == 0
    _teardown()


def test_walk_file_list_only() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.jpg"
    shutil.copy(TEST_JPG_SRC, path)
    path.touch()
    settings = Settings()
    settings.list_only = True
    wos = Walk(settings)
    res = wos.walk_file(path, None)
    assert len(res) == 0
    _teardown()


def test_walk_file_comic() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.cbr"
    shutil.copy(TEST_CBR_SRC, path)
    settings = Settings(None, Namespace(comics=True, bigger=True))
    wos = Walk(settings)
    res = wos.walk_file(path, None)
    assert len(res) == 1
    rep = res.pop().get()
    wos._pool.close()
    wos._pool.join()
    assert rep.final_path == path.with_suffix(".cbz")
    _teardown()


def test_walk_file_dir() -> None:
    _teardown()
    dir_path = TMP_ROOT / "deep"
    dir_path.mkdir(parents=True)
    path = dir_path / "test.txt"
    path.touch()
    settings = Settings()
    wos = Walk(settings)
    res = wos.walk_file(dir_path, None)
    assert len(res) == 0
    _teardown()


def test_walk_dir_unset() -> None:
    _teardown()
    dir_path = TMP_ROOT / "deep"
    dir_path.mkdir(parents=True)
    settings = Settings()
    wos = Walk(settings)
    res = wos.walk_dir(dir_path, None)
    assert len(res) == 0
    _teardown()


def test_walk_dir_recurse() -> None:
    _teardown()
    dir_path = TMP_ROOT / "deep"
    dir_path.mkdir(parents=True)
    settings = Settings()
    wos = Walk(settings)
    res = wos.walk_dir(dir_path, None, True)
    assert len(res) == 0
    _teardown()


# def test_walk_dir_error():
#    _teardown()
#    dir_path = TMP_ROOT / "deep"
#    dir_path.mkdir(parents=True)
#    path = dir_path / "test.txt"
#    path.touch()
#    settings = Settings()
#    wos = Walk(settings)
#    exception = None
#    try:
#        res = wos.walk_dir(dir_path, None)
#    except Exception as exc:
#        exception = exc
#    assert isinstance(exception, Exception)
#    _teardown()


def test_walk_all_files_empty() -> None:
    _teardown()
    wos = Walk(Settings())
    record_dirs, bytes_in, bytes_out, nag, errors = wos._walk_all_files()
    assert len(record_dirs) == 0
    assert bytes_in == 0
    assert bytes_out == 0
    assert not nag
    assert len(errors) == 0
    _teardown()


def test_walk_all_files_one() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.jpg"
    shutil.copy(TEST_JPG_SRC, path)
    wos = Walk(Settings(None, Namespace(paths=[TMP_ROOT], recurse=True)))
    record_dirs, bytes_in, bytes_out, nag, errors = wos._walk_all_files()
    assert len(record_dirs) == 1
    assert bytes_in == 97373
    assert bytes_out == 87922
    assert not nag
    assert len(errors) == 0
    _teardown()


def test_walk_all_files_two() -> None:
    _teardown()
    root1 = TMP_ROOT / "dir1"
    root1.mkdir(parents=True)
    path1 = root1 / "test.jpg"
    shutil.copy(TEST_JPG_SRC, path1)
    root2 = TMP_ROOT / "dir2"
    root2.mkdir()
    path2 = root2 / "test.jpg"
    shutil.copy(TEST_JPG_SRC, path2)
    wos = Walk(Settings(None, Namespace(paths=[root1, root2], recurse=True)))
    record_dirs, bytes_in, bytes_out, nag, errors = wos._walk_all_files()
    assert len(record_dirs) == 2
    assert bytes_in == 194746
    assert bytes_out == 175844
    assert not nag
    assert len(errors) == 0
    _teardown()


def test_walk_all_files_error() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    path = TMP_ROOT / "test.gif"
    shutil.copy(TEST_GIF_SRC, path)
    settings = Settings(
        None,
        Namespace(
            paths=[TMP_ROOT], gifsicle=False, optipng=False, pngout=False, recurse=True
        ),
    )
    wos = Walk(settings)
    record_dirs, bytes_in, bytes_out, nag, errors = wos._walk_all_files()
    assert len(record_dirs) == 1
    assert bytes_in == 0
    assert bytes_out == 0
    assert not nag
    assert len(errors) == 1
    _teardown()


def test_run() -> None:
    _teardown()
    settings = Settings()
    settings.can_do = False
    wos = Walk(settings)
    res = wos.run()
    assert not res
    _teardown()


def test_run_optimize_after() -> None:
    _teardown()
    settings = Settings()
    settings.optimize_after = 3000
    wos = Walk(settings)
    res = wos.run()
    assert res
    _teardown()


def test_run_record_timestamp() -> None:
    _teardown()
    TMP_ROOT.mkdir()
    settings = Settings(
        None, Namespace(record_timestamp=True, paths=[TMP_ROOT], recurse=True)
    )
    wos = Walk(settings)
    res = wos.run()
    assert res
    _teardown()
