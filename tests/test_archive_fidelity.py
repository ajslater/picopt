"""Test archive metadata fidelity through repack: comments, order, times, compression."""

import shutil
from collections.abc import Iterator
from io import BytesIO
from tarfile import LNKTYPE, SYMTYPE, TarFile, TarInfo
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest
from py7zr import SevenZipFile
from py7zr.helpers import ArchiveTimestamp

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
MTIME_TOLERANCE_SECS = 2.0


def _run_picopt(*args: str) -> None:
    cli.main((PROGRAM_NAME, *args, str(TMP_ROOT)))


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
