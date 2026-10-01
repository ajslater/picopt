"""Test archive metadata fidelity through repack: comments, order, times, compression."""

import os
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO, UnsupportedOperation
from pathlib import Path
from stat import S_IFDIR, S_IFLNK, S_IFREG
from tarfile import DIRTYPE, LNKTYPE, SYMTYPE, TarFile, TarInfo
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest
from py7zr import FileInfo, SevenZipFile
from py7zr.helpers import ArchiveTimestamp
from typing_extensions import override

from picopt import PROGRAM_NAME, cli
from picopt.archiveinfo import ArchiveInfo
from picopt.plugins.zip import _fix_zip_filename_encoding
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_FN = "test_png.png"
COMMENT = b"ComicBookInfo metadata lives here"
MEMBER_ORDER = ("zzz_first.txt", PNG_FN, "aaa_last.txt")
TEXT_DATA = b"some text that deflates well " * 10
KNOWN_MTIME = 946684800.0  # 2000-01-01T00:00:00Z
KNOWN_DATE_TIME = (2000, 1, 1, 0, 0, 0)
MTIME_TOLERANCE_SECS = 2.0
DIR_NAME = "pages"
DIR_TEXT_FN = f"{DIR_NAME}/notes.txt"
ZIP_DATA_DESCRIPTOR_FLAG = 0x08
EXEC_FN = "run.sh"
LINK_FN = "run_link.sh"
FILE_MODE = 0o644
EXEC_MODE = 0o755
DIR_MODE = 0o755
GROUP_DIR_MODE = 0o750


def _run_picopt(*args: str) -> None:
    cli.main((PROGRAM_NAME, *args, str(TMP_ROOT)))


def _seven_zip_modes(sz_path: Path) -> dict[str, tuple[int | None, int | None]]:
    """Map each 7z member to its unix file type and permission bits."""
    with SevenZipFile(sz_path, "r") as szf:
        return {f.filename: (f.st_fmt, f.posix_mode) for f in szf.files}


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

    def test_seven_zip_member_mtimes_survive_repack(self) -> None:
        """7z member modification times are restored after repack."""
        sz_path = TMP_ROOT / "timed.7z"
        png_data = (IMAGES_DIR / PNG_FN).read_bytes()
        stamp = ArchiveTimestamp.from_datetime(KNOWN_MTIME)
        with SevenZipFile(sz_path, "w") as szf:
            szf.writef(BytesIO(png_data), PNG_FN)
            header = szf.header
            assert header is not None
            assert header.files_info is not None
            file_info = header.files_info.files[-1]
            file_info["creationtime"] = stamp
            file_info["lastwritetime"] = stamp
            file_info["lastaccesstime"] = stamp
        orig_size = sz_path.stat().st_size

        _run_picopt("-rvx", "7Z,PNG")

        assert sz_path.stat().st_size < orig_size
        with SevenZipFile(sz_path, "r") as szf:
            info = szf.list()[0]
            assert info.creationtime is not None
            assert (
                abs(info.creationtime.timestamp() - KNOWN_MTIME) < MTIME_TOLERANCE_SECS
            )

    def test_seven_zip_directory_survives_repack(self, tmp_path: Path) -> None:
        """A 7z directory member repacks as a directory, not an empty file."""
        src_dir = tmp_path / DIR_NAME
        src_dir.mkdir()
        shutil.copy(IMAGES_DIR / PNG_FN, src_dir / PNG_FN)
        src_dir.chmod(DIR_MODE)
        os.utime(src_dir, (KNOWN_MTIME, KNOWN_MTIME))
        sz_path = TMP_ROOT / "dirs.7z"
        with SevenZipFile(sz_path, "w") as szf:
            szf.writeall(src_dir, DIR_NAME)
        orig_size = sz_path.stat().st_size

        _run_picopt("-rvx", "7Z,PNG")

        assert sz_path.stat().st_size < orig_size
        out_dir = TMP_ROOT / "extracted"
        with SevenZipFile(sz_path, "r") as szf:
            dirinfo = szf.list()[0]
            assert dirinfo.filename == DIR_NAME
            assert dirinfo.is_directory
            assert dirinfo.creationtime is not None
            assert (
                abs(dirinfo.creationtime.timestamp() - KNOWN_MTIME)
                < MTIME_TOLERANCE_SECS
            )
            assert szf.files[0].posix_mode == DIR_MODE
            szf.extract(out_dir)
        assert (out_dir / DIR_NAME / PNG_FN).is_file()

    def test_seven_zip_member_modes_survive_repack(self, tmp_path: Path) -> None:
        """7z members keep their type and permissions, not rw-------."""
        src_dir = tmp_path / DIR_NAME
        src_dir.mkdir()
        png_path = src_dir / PNG_FN
        shutil.copy(IMAGES_DIR / PNG_FN, png_path)
        png_path.chmod(FILE_MODE)
        exec_path = src_dir / EXEC_FN
        exec_path.write_bytes(TEXT_DATA)
        exec_path.chmod(EXEC_MODE)
        (src_dir / LINK_FN).symlink_to(EXEC_FN)
        src_dir.chmod(GROUP_DIR_MODE)
        sz_path = TMP_ROOT / "modes.7z"
        with SevenZipFile(sz_path, "w") as szf:
            szf.writeall(src_dir, DIR_NAME)
        orig_modes = _seven_zip_modes(sz_path)
        assert orig_modes[DIR_NAME] == (S_IFDIR, GROUP_DIR_MODE)
        assert orig_modes[f"{DIR_NAME}/{PNG_FN}"] == (S_IFREG, FILE_MODE)
        assert orig_modes[f"{DIR_NAME}/{EXEC_FN}"] == (S_IFREG, EXEC_MODE)
        assert orig_modes[f"{DIR_NAME}/{LINK_FN}"][0] == S_IFLNK
        orig_size = sz_path.stat().st_size

        _run_picopt("-rvx", "7Z,PNG")

        assert sz_path.stat().st_size < orig_size
        assert _seven_zip_modes(sz_path) == orig_modes

    def test_seven_zip_file_modes_survive_conversion(self, tmp_path: Path) -> None:
        """Converted 7z files keep their permissions; links do not lend theirs."""
        sz_path = TMP_ROOT / "modes.7z"
        with SevenZipFile(sz_path, "w") as szf:
            for name, mode in (("notes.txt", FILE_MODE), (EXEC_FN, EXEC_MODE)):
                src = tmp_path / name
                src.write_bytes(TEXT_DATA)
                src.chmod(mode)
                szf.write(src, name)
            (tmp_path / LINK_FN).symlink_to(EXEC_FN)
            szf.write(tmp_path / LINK_FN, LINK_FN)
        _run_picopt("-rbvx", "7Z,ZIP", "-c", "ZIP")
        zip_path = TMP_ROOT / "modes.zip"
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zf:
            assert zf.getinfo("notes.txt").external_attr >> 16 == S_IFREG | FILE_MODE
            assert zf.getinfo(EXEC_FN).external_attr >> 16 == S_IFREG | EXEC_MODE
            assert zf.getinfo(LINK_FN).external_attr >> 16 == S_IFREG | FILE_MODE


class TestZipFilenameEncoding:
    """Legacy UTF-8 names misread as CP437 are repaired at repack."""

    def test_mojibake_name_repaired(self) -> None:
        real_name = "日本語.png"
        mojibake = real_name.encode("utf-8").decode("cp437")
        zipinfo = ZipInfo(mojibake)
        _fix_zip_filename_encoding(zipinfo)
        assert zipinfo.filename == real_name

    def test_utf8_flagged_name_untouched(self) -> None:
        zipinfo = ZipInfo("日本語.png")
        zipinfo.flag_bits |= 0x800
        _fix_zip_filename_encoding(zipinfo)
        assert zipinfo.filename == "日本語.png"

    def test_ascii_name_untouched(self) -> None:
        zipinfo = ZipInfo("plain.png")
        _fix_zip_filename_encoding(zipinfo)
        assert zipinfo.filename == "plain.png"


class TestArchiveInfoClamp:
    """to_zipinfo clamps un-representable member times."""

    def test_tarinfo_epoch_zero_clamps_to_1980(self) -> None:
        info = TarInfo("x.txt")
        info.mtime = 0
        zipinfo = ArchiveInfo(info).to_zipinfo()
        assert tuple(zipinfo.date_time) == (1980, 1, 1, 0, 0, 0)


class TestArchiveInfoDirectories:
    """to_zipinfo turns directory members into zip directory entries."""

    def test_seven_zip_directory_to_zipinfo(self) -> None:
        mtime = datetime.fromtimestamp(KNOWN_MTIME, tz=UTC)
        info = FileInfo(
            filename=DIR_NAME,
            compressed=None,
            uncompressed=0,
            archivable=True,
            is_directory=True,
            is_file=False,
            is_symlink=False,
            creationtime=mtime,
            crc32=None,
        )
        zipinfo = ArchiveInfo(info).to_zipinfo()
        assert zipinfo.filename == f"{DIR_NAME}/"
        assert zipinfo.is_dir()
        assert tuple(zipinfo.date_time) == KNOWN_DATE_TIME

    def test_file_to_zipinfo_is_not_directory(self) -> None:
        info = TarInfo(DIR_TEXT_FN)
        zipinfo = ArchiveInfo(info).to_zipinfo()
        assert zipinfo.filename == DIR_TEXT_FN
        assert not zipinfo.is_dir()


class TestArchiveInfoFileModes:
    """to_zipinfo gives converted files a regular-file mode."""

    def test_seven_zip_file_to_zipinfo_mode(self) -> None:
        """A 7z member that brings no mode defaults to rw-r--r--."""
        info = FileInfo(
            filename=PNG_FN,
            compressed=None,
            uncompressed=0,
            archivable=True,
            is_directory=False,
            is_file=True,
            is_symlink=False,
            creationtime=None,
            crc32=None,
        )
        zipinfo = ArchiveInfo(info).to_zipinfo()
        assert zipinfo.external_attr >> 16 == S_IFREG | FILE_MODE

    def test_tar_symlink_to_zipinfo_mode(self) -> None:
        """A non-regular tar member does not lend its mode to a zip file."""
        info = TarInfo("link")
        info.type = SYMTYPE
        info.mode = 0o777
        zipinfo = ArchiveInfo(info).to_zipinfo()
        assert zipinfo.external_attr >> 16 == S_IFREG | FILE_MODE
