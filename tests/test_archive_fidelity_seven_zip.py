"""Test 7z archive metadata fidelity through repack and conversion."""

import os
import shutil
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from stat import S_IFDIR, S_IFLNK, S_IFREG
from zipfile import ZipFile

import pytest
from py7zr import SevenZipFile
from py7zr.helpers import ArchiveTimestamp

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_FN = "test_png.png"
TEXT_DATA = b"some text that deflates well " * 10
KNOWN_MTIME = 946684800.0  # 2000-01-01T00:00:00Z
MTIME_TOLERANCE_SECS = 2.0
DIR_NAME = "pages"
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


class TestSevenZipFidelity:
    """Repacked 7z archives must preserve member times, types, and modes."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

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
