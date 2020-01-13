"""Test comic format module."""
import shutil

from pathlib import Path

from picopt.formats.comic import Comic
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring
TEST_FILES_ROOT = Path("tests/test_files")
COMIC_ROOT = TEST_FILES_ROOT / "comic_archives"
TEST_CBR_SRC = COMIC_ROOT / "test_cbr.cbr"
TEST_CBZ_SRC = COMIC_ROOT / "test_cbz.cbz"
TMP_ROOT = Path("/tmp/picopt-test-comic")
TEST_CBZ = TMP_ROOT / "test.cbz"
TEST_ZIP_SIZE = 117


def _setup():
    TMP_ROOT.mkdir(exist_ok=True)


def _teardown():
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_comic_method():
    res = Comic.comics(Settings(), ("a", "b"))
    assert res == "CBZ"


def _test_get_comic_fmt(src, fmt):
    res = Comic.get_comic_format(src)
    assert res == fmt


def test_get_comic_format_cbz() -> None:
    _test_get_comic_fmt(TEST_CBZ_SRC, "CBZ")


def test_get_comic_format_cbr() -> None:
    _test_get_comic_fmt(TEST_CBR_SRC, "CBR")


def test_get_comic_format_neither() -> None:
    src = COMIC_ROOT / "test_cbr.xxx"
    _test_get_comic_fmt(src, None)


def test_get_comic_format_dir() -> None:
    res = Comic.get_comic_format(Path(COMIC_ROOT))
    assert res is None


def test_get_archive_tmp_dir() -> None:
    path = Path("foo")
    res = Comic._get_archive_tmp_dir(path)
    assert res == Path("picopt_tmp_" + str(path))


def _setup_uncompress(fmt: str):
    _setup()
    if fmt == "CBR":
        src = TEST_CBR_SRC
    elif fmt == "CBZ":
        src = TEST_CBZ_SRC
    comic_fn = "test" + src.suffix
    comic_path = TMP_ROOT / comic_fn
    shutil.copy(src, comic_path)

    # comic_size = comic_path.stat().st_size
    uncomp_dir = TMP_ROOT / Path("picopt_tmp_" + comic_fn)
    if uncomp_dir.exists():
        shutil.rmtree(uncomp_dir)

    return comic_path, fmt, uncomp_dir, Settings()


def test_comic_archive_uncompress_unset():
    comic_path, fmt, uncomp_dir, settings = _setup_uncompress("CBZ")

    res = Comic.comic_archive_uncompress(settings, comic_path, fmt)
    assert res[0] is None
    assert res[1] is not None
    assert res[1].final_path == comic_path
    assert res[1].bytes_in == 0
    assert res[1].bytes_out == 0
    _teardown()


def test_comic_archive_uncompress_cbz():
    comic_path, fmt, uncomp_dir, settings = _setup_uncompress("CBZ")
    settings.comics = True
    res = Comic.comic_archive_uncompress(settings, comic_path, fmt)
    assert res[0] == uncomp_dir
    assert res[1] is None
    _teardown()


def test_comic_archive_uncompress_cbr():
    comic_path, fmt, uncomp_dir, settings = _setup_uncompress("CBR")
    settings.comics = True
    settings.verbose = 0
    res = Comic.comic_archive_uncompress(settings, comic_path, fmt)
    assert res[0] == uncomp_dir
    assert res[1] is None
    _teardown()


def test_comic_archive_uncompress_invalid():
    comic_path, fmt, uncomp_dir, settings = _setup_uncompress("CBR")
    settings.comics = True
    res = Comic.comic_archive_uncompress(settings, comic_path, "XXX")
    assert res[0] is None
    assert res[1] is not None
    assert res[1].final_path == comic_path
    _teardown()


def _setup_write_zipfile(old_path):
    tmp_dir = Comic._get_archive_tmp_dir(old_path)
    tmp_dir.mkdir(exist_ok=True, parents=True)
    test_file = tmp_dir / "test.txt"
    test_file.write_text("x")
    return tmp_dir, Settings()


def test_comic_archive_write_zipfile():
    tmp_dir, settings = _setup_write_zipfile(TEST_CBZ)
    assert not TEST_CBZ.is_file()
    Comic._comic_archive_write_zipfile(settings, TEST_CBZ, tmp_dir)
    assert TEST_CBZ.is_file()
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_comic_archive_write_zipfile_quiet():
    tmp_dir, settings = _setup_write_zipfile(TEST_CBZ)
    settings.verbose = 0
    assert not TEST_CBZ.is_file()
    Comic._comic_archive_write_zipfile(settings, TEST_CBZ, tmp_dir)
    assert TEST_CBZ.is_file()
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def _setup_compress(fmt: str):
    old_path, fmt, uncomp_dir, settings = _setup_uncompress(fmt)
    old_size = old_path.stat().st_size
    tmp_dir, settings = _setup_write_zipfile(old_path)
    optimized_archive = old_path.with_suffix(".cbz")
    return old_path, old_size, optimized_archive, settings


def test_comic_archive_compress():
    old_format = "CBR"
    old_path, old_size, optimized_archive, settings = _setup_compress(old_format)
    nag_about_gifs = False
    args = (old_path, old_format, settings, nag_about_gifs)
    assert not optimized_archive.is_file()
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == TEST_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_comic_archive_compress_tmp_path():
    old_format = "CBZ"
    old_path, old_size, optimized_archive, settings = _setup_compress(old_format)
    nag_about_gifs = False
    args = (old_path, old_format, settings, nag_about_gifs)
    assert optimized_archive.is_file()
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == TEST_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_comic_archive_compress_quiet_tmp_path():
    old_format = "CBR"
    old_path, old_size, optimized_archive, settings = _setup_compress(old_format)
    settings.verbose = 0
    nag_about_gifs = False
    args = (old_path, old_format, settings, nag_about_gifs)
    assert not optimized_archive.is_file()
    res = Comic.comic_archive_compress(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == TEST_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_comic_archive_compress_exception():
    old_format = "CBR"
    _, _, _, settings = _setup_compress(old_format)
    nag_about_gifs = False
    args = ("XXXXX", old_format, settings, nag_about_gifs)
    excepted = False
    try:
        Comic.comic_archive_compress(args)
    except Exception:
        excepted = True
        pass
    assert excepted
    _teardown()
