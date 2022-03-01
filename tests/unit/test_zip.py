"""Test comic format module."""
import shutil
import zipfile

from pathlib import Path
from typing import Tuple

from confuse.templates import AttrDict

from picopt.handlers.zip import CBZ, Zip
from tests import CONTAINER_DIR, get_test_dir


__all__ = ()  # hides module from pydocstring
TEST_ZIP_SRC = CONTAINER_DIR / "test_zip.zip"
TEST_CBZ_SRC = CONTAINER_DIR / "test_cbz.cbz"
TMP_ROOT = get_test_dir()
TEST_CBZ = TMP_ROOT / "test.cbz"
TEST_ZIP_SIZE = 117
COMMENT_ZIP_SIZE = 130
EMPTY_STR = b""
TEST_COMMENT = b"test comment"
CONFIG = AttrDict(verbose=1, test=False, bigger=False)


def _setup() -> None:
    TMP_ROOT.mkdir(exist_ok=True)


def _teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def _setup_unpack(fmt: str) -> Tuple[Path, Path, AttrDict]:
    _setup()
    src = Path("/tmp/bad")
    if fmt == Zip.FORMAT_STR:
        src = TEST_ZIP_SRC
    elif fmt == CBZ.FORMAT_STR:
        src = TEST_CBZ_SRC
    assert src != Path("/tmp/bad")
    archive_fn = "test" + src.suffix
    archive_path = TMP_ROOT / archive_fn
    shutil.copy(src, archive_path)
    uncomp_dir = Path(str(archive_path) + CBZ.TMP_SUFFIX)
    return archive_path, uncomp_dir, CONFIG


def test_cbz_unpack() -> None:
    archive_path, uncomp_dir, config = _setup_unpack("CBZ")
    config.formats = set([CBZ.FORMAT])
    tmp_dir, stats, comment = CBZ.unpack(config, archive_path)
    assert tmp_dir == uncomp_dir
    assert stats is None
    assert comment == EMPTY_STR
    _teardown()


def test_unpack_cbz_dirty() -> None:
    archive_path, uncomp_dir, config = _setup_unpack("CBZ")
    config.formats = set([CBZ.FORMAT])
    uncomp_dir.mkdir(exist_ok=True)
    tmp_dir, stats, comment = CBZ.unpack(config, archive_path)
    assert tmp_dir == uncomp_dir
    assert stats is None
    assert comment == EMPTY_STR
    _teardown()


def test_unpack_zip() -> None:
    archive_path, uncomp_dir, config = _setup_unpack("ZIP")
    config.formats = set([Zip.FORMAT])
    config.verbose = 0
    tmp_dir, stats, comment = Zip.unpack(config, archive_path)
    assert tmp_dir == uncomp_dir
    assert stats is None
    assert comment == TEST_COMMENT
    _teardown()


def test_unpack_invalid() -> None:
    tmp_dir, stats, comment = Zip.unpack(CONFIG, TMP_ROOT)
    assert tmp_dir is None
    assert stats is not None
    assert stats.final_path == TMP_ROOT
    assert comment is None
    _teardown()


def _setup_write_zipfile(old_path: Path) -> Tuple[Path, AttrDict]:
    tmp_dir = Zip.get_tmp_path(old_path)
    tmp_dir.mkdir(exist_ok=True, parents=True)
    test_file = tmp_dir / "test.txt"
    test_file.write_text("x")
    return tmp_dir, CONFIG


def test_create_container() -> None:
    tmp_dir, config = _setup_write_zipfile(TEST_CBZ)
    assert not TEST_CBZ.is_file()
    CBZ.create_container(config, TEST_CBZ, tmp_dir, EMPTY_STR)
    assert TEST_CBZ.is_file()
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_create_container_quiet() -> None:
    tmp_dir, config = _setup_write_zipfile(TEST_CBZ)
    config.verbose = 0
    assert not TEST_CBZ.is_file()
    CBZ.create_container(config, TEST_CBZ, tmp_dir, EMPTY_STR)
    assert TEST_CBZ.is_file()
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def _setup_repack(
    handler: ContainerHandler, src: Path
) -> Tuple[Path, int, Path, AttrDict]:
    old_path = TMP_ROOT / src.name
    tmp_dir = handler.get_tmp_path(old_path)
    tmp_dir.mkdir(exist_ok=True, parents=True)
    tmp_contents = tmp_dir / "foo.txt"
    tmp_contents.touch(exist_ok=True)
    new_path = old_path.with_suffix(handler.SUFFIX)
    return old_path, tmp_dir, new_path


def test_repack() -> None:
    handler = Zip
    old_path, tmp_dir, new_path = _setup_repack(handler, TEST_ZIP_SRC)
    args = (old_path, CONFIG, TEST_COMMENT)
    res = handler.repack(args)
    assert new_path.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == COMMENT_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == COMMENT_ZIP_SIZE
    with zipfile.ZipFile(res.final_path, "r") as zf:
        assert zf.comment == TEST_COMMENT
    _teardown()


def test_repack_tmp_path() -> None:
    handler = CBZ
    old_path, old_size, optimized_archive, config = _setup_repack(handler.FORMAT_STR)
    args = (old_path, config, EMPTY_STR)
    import os

    assert optimized_archive.is_file()
    print(os.listdir(optimized_archive.parent))
    res = handler.repack(args)
    print(os.listdir(optimized_archive.parent))
    assert optimized_archive.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == TEST_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_repack_quiet_tmp_path() -> None:
    handler = CBZ
    old_format = handler.FORMAT_STR
    old_path, old_size, optimized_archive, config = _setup_repack(old_format)
    config.verbose = 0
    args = (old_path, config, EMPTY_STR)
    assert not optimized_archive.is_file()
    res = handler.repack(args)
    assert optimized_archive.is_file()
    assert res.bytes_in == old_size
    assert res.bytes_out == TEST_ZIP_SIZE
    assert TEST_CBZ.stat().st_size == TEST_ZIP_SIZE
    _teardown()


def test_repack_exception() -> None:
    handler = CBZ
    old_format = handler.FORMAT_STR
    _, _, _, config = _setup_repack(old_format)
    TMP_ROOT.mkdir(exist_ok=True)
    path = TMP_ROOT / "XXXXX"
    args = (path, config, EMPTY_STR)
    excepted = False
    try:
        handler.repack(args)
    except Exception:
        excepted = True
        pass
    assert excepted
    _teardown()
