"""Test gif module."""
import shutil

from argparse import Namespace

from picopt.settings import Settings
from picopt.stats import ReportStats
from picopt.timestamp import OLD_TIMESTAMP_FN
from picopt.timestamp import Timestamp
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


class TestWalk:
    def setup_method(self):
        self.teardown_method()
        TMP_ROOT.mkdir()
        self.settings = Settings(check_programs=True)
        self.wob = Walk()
        self.wob._timestamps[TMP_ROOT] = Timestamp(self.settings, TMP_ROOT)

    def teardown_method(self):
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_comic_archive_skip(self) -> None:
        path = TMP_ROOT / "xxx"
        rep = ReportStats(path)
        res = Walk._comic_archive_skip((rep,))
        assert res.final_path == path

    def test_walk_comic_archive_skip(self) -> None:
        cbr = TMP_ROOT / "test.cbr"
        # cbz = TMP_ROOT / "test.cbz"
        shutil.copy(TEST_CBR_SRC, cbr)
        # old_size = cbr.stat().st_size
        result_set = self.wob.walk_comic_archive(cbr, "CBR", None, self.settings)
        res = result_set.pop()
        rep = res.get()
        assert not rep.error
        assert rep.final_path == cbr
        assert rep.bytes_in == 0
        assert rep.bytes_out == 0
        self.wob._pool.close()
        self.wob._pool.join()

    def test_walk_comic_archive_bigger(self) -> None:
        cbr = TMP_ROOT / "test.cbr"
        cbz = TMP_ROOT / "test.cbz"
        shutil.copy(TEST_CBR_SRC, cbr)
        old_size = cbr.stat().st_size
        self.settings.comics = True
        self.settings.bigger = True
        result_set = self.wob.walk_comic_archive(cbr, "CBR", None, self.settings)
        res = result_set.pop()
        rep = res.get()
        assert not rep.error
        assert rep.final_path == cbz
        assert rep.bytes_in == old_size
        assert rep.bytes_out > 0
        self.wob._pool.close()
        self.wob._pool.join()

    def test_is_skippable_unset(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.touch()
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert not res

    def test_is_skippable_symlink(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.symlink_to(TMP_ROOT)
        self.settings.follow_symlinks = False
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert res

    def test_is_skippable_symlink_quiet(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.symlink_to(TMP_ROOT)
        self.settings.follow_symlinks = False
        self.settings.verbose = 0
        self.wob._timestamps[TMP_ROOT] = Timestamp(self.settings, TMP_ROOT)
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert res

    def test_is_skippable_timestamp(self) -> None:
        path = TMP_ROOT / OLD_TIMESTAMP_FN
        path.touch()
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert res

    def test_is_skippable_dne(self) -> None:
        path = TMP_ROOT / "test.txt"
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert res

    def test_is_skippable_quiet(self) -> None:
        path = TMP_ROOT / "test.txt"
        self.settings.verbose = 0
        res = self.wob._is_skippable(path, self.settings, TMP_ROOT)
        assert res

    def test_is_older_than_timestamp_none(self) -> None:
        res = Walk._is_older_than_timestamp(TMP_ROOT, None, None)
        assert not res

    def test_is_older_than_timestamp_older(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.touch()
        walk_after = path.stat().st_mtime + 100
        res = Walk._is_older_than_timestamp(path, walk_after, None)
        assert res

    def test_is_older_than_timestamp_same(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.touch()
        walk_after = path.stat().st_mtime
        res = Walk._is_older_than_timestamp(path, walk_after, None)
        assert res

    def test_is_older_than_timestamp_newer(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.touch()
        walk_after = path.stat().st_mtime - 100
        res = Walk._is_older_than_timestamp(path, walk_after, None)
        assert not res

    def test_is_older_than_timestamp_older_archive(self) -> None:
        path = TMP_ROOT / "test.txt"
        path.touch()
        walk_after = path.stat().st_mtime - 100
        archive_mtime = walk_after + 200
        res = Walk._is_older_than_timestamp(path, walk_after, archive_mtime)
        assert not res

    def test_walk_file_older_than(self) -> None:
        path = TMP_ROOT / "text.txt"
        path.touch()
        walk_after = path.stat().st_mtime
        res = self.wob.walk_file(path, walk_after, self.settings, TMP_ROOT)
        assert len(res) == 0

    def test_walk_file_list_only(self) -> None:
        path = TMP_ROOT / "test.jpg"
        shutil.copy(TEST_JPG_SRC, path)
        path.touch()
        self.settings.list_only = True
        res = self.wob.walk_file(path, None, self.settings, TMP_ROOT)
        assert len(res) == 0

    def test_walk_file_comic(self) -> None:
        path = TMP_ROOT / "test.cbr"
        shutil.copy(TEST_CBR_SRC, path)
        self.settings.comics = True
        self.settings.bigger = True
        self.settings._update_formats()
        res = self.wob.walk_file(path, None, self.settings, TMP_ROOT)
        assert len(res) == 1
        rep = res.pop().get()
        self.wob._pool.close()
        self.wob._pool.join()
        assert rep.final_path == path.with_suffix(".cbz")

    def test_walk_file_dir(self) -> None:
        dir_path = TMP_ROOT / "deep"
        dir_path.mkdir(parents=True)
        path = dir_path / "test.txt"
        path.touch()
        res = self.wob.walk_file(dir_path, None, self.settings, TMP_ROOT)
        assert len(res) == 0

    def test_walk_dir_unset(self) -> None:
        dir_path = TMP_ROOT / "deep"
        dir_path.mkdir(parents=True)
        res = self.wob.walk_dir(dir_path, None, self.settings, TMP_ROOT)
        assert len(res) == 0

    def test_walk_dir_recurse(self) -> None:
        dir_path = TMP_ROOT / "deep"
        dir_path.mkdir(parents=True)
        res = self.wob.walk_dir(dir_path, None, self.settings, TMP_ROOT, True)
        assert len(res) == 0

    # def test_walk_dir_error():
    #    _teardown()
    #    dir_path = TMP_ROOT / "deep"
    #    dir_path.mkdir(parents=True)
    #    path = dir_path / "test.txt"
    #    path.touch()
    #    wos = Walk()
    #    exception = None
    #    try:
    #        res = self.wob.walk_dir(dir_path, None)
    #    except Exception as exc:
    #        exception = exc
    #    assert isinstance(exception, Exception)
    #    _teardown()

    def test_walk_all_files_empty(self) -> None:
        bytes_in, bytes_out, nag, errors = self.wob._walk_all_files(
            self.settings, set([TMP_ROOT])
        )
        assert bytes_in == 0
        assert bytes_out == 0
        assert not nag
        assert len(errors) == 0

    def test_walk_all_files_one(self) -> None:
        path = TMP_ROOT / "test.jpg"
        shutil.copy(TEST_JPG_SRC, path)
        self.settings.arg_namespace = Namespace(**{"recurse": True})
        bytes_in, bytes_out, nag, errors = self.wob._walk_all_files(
            self.settings, set([TMP_ROOT])
        )
        assert bytes_in == 97373
        assert bytes_out == 87922
        assert not nag
        assert len(errors) == 0

    def test_walk_all_files_two(self) -> None:
        root1 = TMP_ROOT / "dir1"
        root1.mkdir(parents=True)
        path1 = root1 / "test.jpg"
        shutil.copy(TEST_JPG_SRC, path1)
        root2 = TMP_ROOT / "dir2"
        root2.mkdir(parents=True)
        path2 = root2 / "test.jpg"
        shutil.copy(TEST_JPG_SRC, path2)
        self.settings.arg_namespace = Namespace(**{"recurse": True})
        bytes_in, bytes_out, nag, errors = self.wob._walk_all_files(
            self.settings, set([root1, root2])
        )
        assert bytes_in == 194746
        assert bytes_out == 175844
        assert not nag
        assert len(errors) == 0

    def test_walk_all_files_error(self) -> None:
        path = TMP_ROOT / "test.gif"
        shutil.copy(TEST_GIF_SRC, path)

        self.settings = Settings(
            arg_namespace=Namespace(
                gifsicle=False, optipng=False, pngout=False, recurse=True
            )
        )
        print(f"{self.settings.formats=}")
        bytes_in, bytes_out, nag, errors = self.wob._walk_all_files(
            self.settings, set([TMP_ROOT])
        )
        assert bytes_in == 0
        assert bytes_out == 0
        assert not nag
        assert len(errors) == 1

    def test_run(self) -> None:
        self.settings.can_do = False
        res = self.wob.run(self.settings)
        assert not res

    def test_run_optimize_after(self) -> None:
        self.settings.optimize_after = 3000
        res = self.wob.run(self.settings)
        assert res

    def test_run_record_timestamp(self) -> None:
        self.settings.record_timestamps = True
        self.settings.paths = set([TMP_ROOT])
        res = self.wob.run(self.settings)
        assert res
