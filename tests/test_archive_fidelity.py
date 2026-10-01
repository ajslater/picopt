"""Test archive metadata fidelity through repack: comments, order, times, compression."""

import shutil
from collections.abc import Iterator
from io import BytesIO, UnsupportedOperation
from pathlib import Path
from stat import S_IFREG
from tarfile import DIRTYPE, LNKTYPE, SYMTYPE, TarFile, TarInfo
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest
from typing_extensions import override

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_FN = "test_png.png"
COMMENT = b"ComicBookInfo metadata lives here"
MEMBER_ORDER = ("zzz_first.txt", PNG_FN, "aaa_last.txt")
TEXT_DATA = b"some text that deflates well " * 10
KNOWN_MTIME = 946684800.0  # 2000-01-01T00:00:00Z
KNOWN_DATE_TIME = (2000, 1, 1, 0, 0, 0)
DIR_NAME = "pages"
DIR_TEXT_FN = f"{DIR_NAME}/notes.txt"
ZIP_DATA_DESCRIPTOR_FLAG = 0x08
EXEC_FN = "run.sh"
FILE_MODE = 0o644
EXEC_MODE = 0o755


def _run_picopt(*args: str) -> None:
    cli.main((PROGRAM_NAME, *args, str(TMP_ROOT)))


class _UnseekableBuffer(BytesIO):
    """A stream ZipFile cannot seek, so it writes data descriptors."""

    @override
    def seek(self, _offset: int, _whence: int = 0, /) -> int:
        raise UnsupportedOperation


def _assert_zip_dir_entry(zip_path: Path) -> ZipInfo:
    """Assert the directory is a header-only entry, not an empty regular file."""
    with ZipFile(zip_path, "r") as zf:
        assert zf.testzip() is None
        assert DIR_NAME not in zf.namelist()
        dirinfo = zf.getinfo(f"{DIR_NAME}/")
        assert dirinfo.is_dir()
        assert dirinfo.compress_type == ZIP_STORED
        assert dirinfo.compress_size == dirinfo.file_size == 0
        assert not dirinfo.flag_bits & ZIP_DATA_DESCRIPTOR_FLAG
        out_dir = TMP_ROOT / "extracted"
        for info in zf.infolist():
            zf.extract(info, out_dir)
    assert (out_dir / DIR_NAME).is_dir()
    return dirinfo


class TestArchiveFidelity:
    """Repacked archives must preserve comments, order, and sane metadata."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_zip_comment_preserved_on_repack(self) -> None:
        """An archive comment survives optimization."""
        zip_path = TMP_ROOT / "commented.cbz"
        with ZipFile(zip_path, "w") as zf:
            zf.write(IMAGES_DIR / PNG_FN, PNG_FN)
            zf.comment = COMMENT
        _run_picopt("-rvx", "CBZ,PNG")
        with ZipFile(zip_path, "r") as zf:
            assert zf.comment == COMMENT
            assert zf.namelist() == [PNG_FN]

    def test_member_order_preserved_on_repack(self) -> None:
        """Members come back in their original, non-alphabetical order."""
        zip_path = TMP_ROOT / "ordered.cbz"
        with ZipFile(zip_path, "w") as zf:
            for name in MEMBER_ORDER:
                if name == PNG_FN:
                    zf.write(IMAGES_DIR / PNG_FN, PNG_FN)
                else:
                    zf.writestr(name, TEXT_DATA)
        _run_picopt("-rvx", "CBZ,PNG")
        with ZipFile(zip_path, "r") as zf:
            assert tuple(zf.namelist()) == MEMBER_ORDER

    def test_pre_1980_member_times_clamped_on_conversion(self) -> None:
        """Tar members with epoch-zero mtimes convert without crashing."""
        tar_path = TMP_ROOT / "old.tar"
        with TarFile(tar_path, "w") as tf:
            info = TarInfo("ancient.txt")
            info.size = len(TEXT_DATA)
            info.mtime = 0
            tf.addfile(info, BytesIO(TEXT_DATA))
        _run_picopt("-rvx", "TAR,ZIP", "-c", "ZIP")
        zip_path = TMP_ROOT / "old.zip"
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zf:
            zipinfo = zf.getinfo("ancient.txt")
            assert zipinfo.date_time == (1980, 1, 1, 0, 0, 0)
            assert zf.read("ancient.txt") == TEXT_DATA

    def test_conversion_compresses_by_content(self) -> None:
        """Converted members deflate text but store already-compressed images."""
        tar_path = TMP_ROOT / "mixed.tar"
        with TarFile(tar_path, "w") as tf:
            tf.add(IMAGES_DIR / PNG_FN, PNG_FN)
            info = TarInfo("notes.txt")
            info.size = len(TEXT_DATA)
            tf.addfile(info, BytesIO(TEXT_DATA))
        _run_picopt("-rvx", "TAR,ZIP", "-c", "ZIP")
        zip_path = TMP_ROOT / "mixed.zip"
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zf:
            assert zf.getinfo("notes.txt").compress_type == ZIP_DEFLATED
            assert zf.getinfo(PNG_FN).compress_type == ZIP_STORED

    def test_tar_file_modes_survive_conversion(self) -> None:
        """Converted tar members keep their permissions as regular zip files."""
        tar_path = TMP_ROOT / "modes.tar"
        with TarFile(tar_path, "w") as tf:
            for name, mode in (("notes.txt", FILE_MODE), (EXEC_FN, EXEC_MODE)):
                info = TarInfo(name)
                info.size = len(TEXT_DATA)
                info.mode = mode
                tf.addfile(info, BytesIO(TEXT_DATA))
        _run_picopt("-rvx", "TAR,ZIP", "-c", "ZIP")
        zip_path = TMP_ROOT / "modes.zip"
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zf:
            assert zf.getinfo("notes.txt").external_attr >> 16 == S_IFREG | FILE_MODE
            assert zf.getinfo(EXEC_FN).external_attr >> 16 == S_IFREG | EXEC_MODE

    def test_tar_directory_converts_to_zip_directory(self) -> None:
        """A tar directory member becomes a zip directory entry."""
        tar_path = TMP_ROOT / "dirs.tar"
        with TarFile(tar_path, "w") as tf:
            dirinfo = TarInfo(DIR_NAME)
            dirinfo.type = DIRTYPE
            dirinfo.mode = 0o755
            dirinfo.mtime = KNOWN_MTIME
            tf.addfile(dirinfo)
            info = TarInfo(DIR_TEXT_FN)
            info.size = len(TEXT_DATA)
            tf.addfile(info, BytesIO(TEXT_DATA))
        _run_picopt("-rvx", "TAR,ZIP", "-c", "ZIP")
        zip_path = TMP_ROOT / "dirs.zip"
        assert zip_path.exists()
        dirinfo = _assert_zip_dir_entry(zip_path)
        assert dirinfo.date_time == KNOWN_DATE_TIME
        assert (TMP_ROOT / "extracted" / DIR_TEXT_FN).read_bytes() == TEXT_DATA

    def test_zip_directory_survives_repack(self) -> None:
        """A deflated, data-descriptor directory entry repacks header-only."""
        buf = _UnseekableBuffer()
        with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
            zf.writestr(f"{DIR_NAME}/", b"")
            zf.write(IMAGES_DIR / PNG_FN, f"{DIR_NAME}/{PNG_FN}")
        source_dirinfo = ZipFile(BytesIO(buf.getvalue())).getinfo(f"{DIR_NAME}/")
        assert source_dirinfo.compress_size > 0
        assert source_dirinfo.flag_bits & ZIP_DATA_DESCRIPTOR_FLAG
        zip_path = TMP_ROOT / "dirs.zip"
        zip_path.write_bytes(buf.getvalue())
        orig_size = zip_path.stat().st_size

        _run_picopt("-rvx", "ZIP,PNG")

        assert zip_path.stat().st_size < orig_size
        _assert_zip_dir_entry(zip_path)
        assert (TMP_ROOT / "extracted" / DIR_NAME / PNG_FN).is_file()

    def test_tar_links_survive_repack(self) -> None:
        """Symlinks and hardlinks keep their type and target through repack."""
        tar_path = TMP_ROOT / "links.tar"
        with TarFile(tar_path, "w") as tf:
            tf.add(IMAGES_DIR / PNG_FN, PNG_FN)
            info = TarInfo("notes.txt")
            info.size = len(TEXT_DATA)
            tf.addfile(info, BytesIO(TEXT_DATA))
            symlink = TarInfo("link_to_notes.txt")
            symlink.type = SYMTYPE
            symlink.linkname = "notes.txt"
            tf.addfile(symlink)
            hardlink = TarInfo("hardlink_to_notes.txt")
            hardlink.type = LNKTYPE
            hardlink.linkname = "notes.txt"
            tf.addfile(hardlink)
        orig_size = tar_path.stat().st_size

        _run_picopt("-rvx", "TAR,PNG")

        assert tar_path.stat().st_size < orig_size
        with TarFile(tar_path, "r") as tf:
            symlink = tf.getmember("link_to_notes.txt")
            assert symlink.type == SYMTYPE
            assert symlink.linkname == "notes.txt"
            assert symlink.size == 0
            hardlink = tf.getmember("hardlink_to_notes.txt")
            assert hardlink.type == LNKTYPE
            assert hardlink.linkname == "notes.txt"
            assert hardlink.size == 0
            member = tf.extractfile("notes.txt")
            assert member is not None
            assert member.read() == TEXT_DATA
