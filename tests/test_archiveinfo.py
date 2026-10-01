"""Test ArchiveInfo member conversion and zip filename repair."""

from datetime import UTC, datetime
from stat import S_IFREG
from tarfile import SYMTYPE, TarInfo
from zipfile import ZipInfo

from py7zr import FileInfo

from picopt.archiveinfo import ArchiveInfo
from picopt.plugins.zip import _fix_zip_filename_encoding

__all__ = ()

PNG_FN = "test_png.png"
KNOWN_MTIME = 946684800.0  # 2000-01-01T00:00:00Z
KNOWN_DATE_TIME = (2000, 1, 1, 0, 0, 0)
DIR_NAME = "pages"
DIR_TEXT_FN = f"{DIR_NAME}/notes.txt"
FILE_MODE = 0o644


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
