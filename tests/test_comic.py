"""Test comic format module."""
import shutil

from pathlib import Path
from unittest import TestCase

from picopt.formats.comic import Comic
from picopt.settings import Settings


TEST_FILES_ROOT = "tests/test_files"
COMIC_ROOT = TEST_FILES_ROOT + "/comic_archives"
SETTINGS = Settings()
__all__ = ()  # hides module from pydocstring


def test_comic_method():
    res = Comic.comics(SETTINGS, ("a", "b"))
    assert res == "CBZ"


class TestGetComicFormat(TestCase):
    def test_cbz(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT + "/test_cbz.cbz"))
        self.assertEqual(res, "CBZ")

    def test_cbr(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT + "/test_cbr.cbr"))
        self.assertEqual(res, "CBR")

    def test_neither(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT + "/test_cbr.xxx"))
        self.assertEqual(res, None)

    def test_dir(self) -> None:
        res = Comic.get_comic_format(Path(COMIC_ROOT))
        self.assertIsNone(res)


class TestGetArchiveTmpDir(TestCase):
    def test_foo(self) -> None:
        res = Comic._get_archive_tmp_dir(Path("foo"))
        self.assertEqual(str(res), "picopt_tmp_foo")


def test_comic_archive_uncompress_unset():
    comic_path = Path(COMIC_ROOT + "/test_cbr.cbr")
    # comic_size = comic_path.stat().st_size

    res = Comic.comic_archive_uncompress(SETTINGS, comic_path, "CBZ")
    assert res[0] is None
    assert res[1] is not None
    assert res[1].final_path == comic_path
    assert res[1].bytes_in == 0
    assert res[1].bytes_out == 0


def test_comic_archive_uncompress_cbz():
    settings = Settings(set(), SETTINGS)
    settings.comics = True
    comic_fn = "test_cbz.cbz"
    comic_path = Path(COMIC_ROOT + "/" + comic_fn)
    # comic_size = comic_path.stat().st_size
    uncomp_dir = Path(COMIC_ROOT + "/" + "picopt_tmp_" + comic_fn)

    if uncomp_dir.exists():
        shutil.rmtree(uncomp_dir)
    res = Comic.comic_archive_uncompress(settings, comic_path, "CBZ")
    assert res[0] == uncomp_dir
    assert res[1] is None


def test_comic_archive_uncompress_cbr():
    settings = Settings(set(), SETTINGS)
    settings.comics = True
    settings.verbose = 0
    comic_fn = "test_cbr.cbr"
    comic_path = Path(COMIC_ROOT + "/" + comic_fn)
    # comic_size = comic_path.stat().st_size
    uncomp_dir = Path(COMIC_ROOT + "/" + "picopt_tmp_" + comic_fn)

    res = Comic.comic_archive_uncompress(settings, comic_path, "CBR")
    assert res[0] == uncomp_dir
    assert res[1] is None


def test_comic_archive_uncompress_invalid():
    settings = Settings(set(), SETTINGS)
    settings.comics = True
    comic_fn = "test_cbr.cbr"
    comic_path = Path(COMIC_ROOT + "/" + comic_fn)
    # comic_size = comic_path.stat().st_size
    # uncomp_dir = Path(COMIC_ROOT + "/" + "picopt_tmp_" + comic_fn)

    res = Comic.comic_archive_uncompress(settings, comic_path, "XXX")
    assert res[0] is None
    assert res[1] is not None
    assert res[1].final_path == comic_path


def _setup_write_zipfile():
    settings = Settings(set(), SETTINGS)
    tmp_path = Path("/tmp/comic_test_dir")
    test_file = tmp_path / "test.txt"
    tmp_path.mkdir()
    test_file.write_text("x")
    new_path = Path("/tmp/comic_test.cbz")
    return settings, new_path, tmp_path


def _teardown_write_zipfile(tmp_path, new_path):
    if tmp_path.is_dir():
        shutil.rmtree(tmp_path)
    if new_path.exists():
        new_path.unlink()


def test_comic_archive_write_zipfile():
    settings, new_path, tmp_path = _setup_write_zipfile()

    Comic._comic_archive_write_zipfile(settings, new_path, tmp_path)
    assert new_path.is_file()
    _teardown_write_zipfile(tmp_path, new_path)


def test_comic_archive_write_zipfile_quiet():
    settings, new_path, tmp_path = _setup_write_zipfile()
    settings.verbose = 0

    Comic._comic_archive_write_zipfile(settings, new_path, tmp_path)
    assert new_path.is_file()
    _teardown_write_zipfile(tmp_path, new_path)


def test_comic_archive_compress():
    settings, path, tmp_path = _setup_write_zipfile()
    optimized_archive = Path("/tmp/comic_test.picopt-optimized.cbz")
    old_format = "CBR"
    settings = Settings(set(), SETTINGS)
    nag_about_gifs = False
    args = (path, old_format, settings, nag_about_gifs)
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    _teardown_write_zipfile(tmp_path, optimized_archive)


def test_comic_archive_compress_tmp_path():
    settings, path, tmp_path = _setup_write_zipfile()
    optimized_archive = Path("/tmp/comic_test.picopt-optimized.cbz")
    tmp_zip = Path("/tmp/picopt_tmp_comic_test.cbz")
    tmp_zip.mkdir()
    old_format = "CBR"
    settings = Settings(set(), SETTINGS)
    nag_about_gifs = False
    args = (path, old_format, settings, nag_about_gifs)
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    _teardown_write_zipfile(tmp_path, optimized_archive)


def test_comic_archive_compress_quiet_tmp_path():
    settings, path, tmp_path = _setup_write_zipfile()
    optimized_archive = Path("/tmp/comic_test.picopt-optimized.cbz")
    tmp_zip = Path("/tmp/picopt_tmp_comic_test.cbz")
    tmp_zip.mkdir()
    old_format = "CBR"
    settings = Settings(set(), SETTINGS)
    settings.verbose = 0
    nag_about_gifs = False
    args = (path, old_format, settings, nag_about_gifs)
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == 0
    assert res.bytes_out == 0
    _teardown_write_zipfile(tmp_path, optimized_archive)


def test_comic_archive_compress_exception():
    settings, path, tmp_path = _setup_write_zipfile()
    optimized_archive = Path("/tmp/comic_test.picopt-optimized.cbz")
    old_format = "CBR"
    settings = Settings(set(), SETTINGS)
    nag_about_gifs = False
    path = "XXXXX"
    args = (path, old_format, settings, nag_about_gifs)
    excepted = False
    try:
        Comic.comic_archive_compress(args)
    except Exception:
        excepted = True
        pass
    assert excepted
    _teardown_write_zipfile(tmp_path, optimized_archive)
