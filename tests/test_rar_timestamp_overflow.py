"""
Test the rarfile sub-second timestamp overflow patch.

rarfile <= 4.5 crashes opening a RAR3 archive whose extended mtime carries
a sub-second remainder of a second or more. See picopt/plugins/rar.py.

Importing picopt's RAR plugin patches the rarfile module for the whole
process, so no test here may assert the unpatched behavior in process.
test_fixture_crashes_pristine_rarfile uses a subprocess for that.
"""

import struct
import subprocess
import sys
from binascii import crc32
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
import rarfile

from picopt import PROGRAM_NAME, cli
from picopt.archiveinfo import ArchiveInfo
from picopt.plugins.rar import _patch_nsec_overflow
from tests import IMAGES_DIR

__all__ = ()

_S_BLOCK_HEADER = struct.Struct("<HBHH")  # crc, type, flags, size
_S_FILE_HEADER = struct.Struct("<LLBLLBBHL")
_RAR3_MARKER = b"Rar!\x1a\x07\x00"
_BLOCK_MAIN = 0x73
_BLOCK_FILE = 0x74
_FLAG_EXTTIME = 0x1000
_FLAG_LONG_BLOCK = 0x8000
# mtime nibble of the exttime flags word: present, with 3 remainder bytes.
_EXTTIME_MTIME_3_BYTES = 0xB000
_METHOD_STORED = 0x30
_MEMBER_FN = "test_png.png"
_MEMBER_DATA = (IMAGES_DIR / _MEMBER_FN).read_bytes()

# Sub-second remainder in 100ns units: 1_232_076_000ns, as written by the
# third-party packer in comicbox's codex #820 report.
_OVERFLOW_REMAINDER = 12_320_760
_OVERFLOW_NSEC = _OVERFLOW_REMAINDER * 100
_UPSTREAM_ERROR = "microsecond must be in 0..999999"

_FIXTURE_DTTM = datetime(2020, 3, 15, 10, 30, 24)  # noqa: DTZ001
_FIXTURE_DOSTIME = (
    ((2020 - 1980) << 25) | (3 << 21) | (15 << 16) | (10 << 11) | (30 << 5) | (24 // 2)
)
# The remainder carries a whole second out, leaving 232076 microseconds.
_FIXTURE_MTIME = datetime(2020, 3, 15, 10, 30, 25, 232076)  # noqa: DTZ001

_NS_PER_SECOND = 1_000_000_000
_MAX_RAR3_NSEC = 0xFFFFFF * 100  # widest remainder three bytes can encode


def _rar3_block(block_type: int, flags: int, body: bytes) -> bytes:
    """Frame a RAR3 block, checksumming everything after the crc field."""
    size = _S_BLOCK_HEADER.size + len(body)
    raw = _S_BLOCK_HEADER.pack(0, block_type, flags, size) + body
    crc = crc32(raw[2:]) & 0xFFFF
    return _S_BLOCK_HEADER.pack(crc, block_type, flags, size) + body


def _write_overflow_rar(path: Path) -> Path:
    """
    Write a RAR3 archive whose one member's mtime remainder exceeds a second.

    The member is stored, so rarfile reads it without unrar. The remainder
    bytes are little endian: rarfile accumulates them as
    ``rem = (b << 16) | (rem >> 8)``.
    """
    name = _MEMBER_FN.encode()
    exttime = struct.pack("<H", _EXTTIME_MTIME_3_BYTES) + bytes(
        (
            _OVERFLOW_REMAINDER & 0xFF,
            (_OVERFLOW_REMAINDER >> 8) & 0xFF,
            (_OVERFLOW_REMAINDER >> 16) & 0xFF,
        )
    )
    file_body = (
        _S_FILE_HEADER.pack(
            len(_MEMBER_DATA),  # pack size
            len(_MEMBER_DATA),  # unpacked size
            0,  # host os: MS-DOS
            crc32(_MEMBER_DATA),
            _FIXTURE_DOSTIME,
            20,  # version needed
            _METHOD_STORED,
            len(name),
            0x20,  # attributes: archive
        )
        + name
        + exttime
    )
    path.write_bytes(
        _RAR3_MARKER
        + _rar3_block(_BLOCK_MAIN, 0, bytes(6))
        + _rar3_block(_BLOCK_FILE, _FLAG_LONG_BLOCK | _FLAG_EXTTIME, file_body)
        + _MEMBER_DATA
    )
    return path


def test_fixture_crashes_pristine_rarfile(tmp_path: Path) -> None:
    """
    The fixture really does crash unpatched rarfile.

    A fresh interpreter that never imports picopt, so the patch can't mask
    the upstream bug. Without this the fix could keep passing against a
    fixture that stopped reproducing the crash.
    """
    rar_path = _write_overflow_rar(tmp_path / "overflow.cbr")
    script = f"import rarfile; rarfile.RarFile({str(rar_path)!r})"

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], check=False, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert _UPSTREAM_ERROR in result.stderr


def test_rar_opens_with_carried_mtime(tmp_path: Path) -> None:
    """The archive opens and the member mtime carries the whole second."""
    rar_path = _write_overflow_rar(tmp_path / "overflow.cbr")

    with rarfile.RarFile(rar_path) as archive:
        (info,) = archive.infolist()
        assert archive.read(info) == _MEMBER_DATA

    assert info.mtime == _FIXTURE_MTIME
    # picopt turns a RarInfo into a ZipInfo at once, dropping the sub-seconds.
    assert ArchiveInfo(info).datetime() == _FIXTURE_MTIME.replace(
        microsecond=0, tzinfo=UTC
    )


def test_cbr_converts_to_cbz(tmp_path: Path) -> None:
    """Workers open the archive too, so the conversion keeps the mtime."""
    rar_path = _write_overflow_rar(tmp_path / "overflow.cbr")

    cli.main((PROGRAM_NAME, "-x", "CBR,CBZ", "-c", "CBZ", str(rar_path)))

    assert not rar_path.exists()
    with ZipFile(tmp_path / "overflow.cbz") as archive:
        (info,) = archive.infolist()
    assert info.filename == _MEMBER_FN
    # Zip stores even seconds only.
    assert info.date_time == (2020, 3, 15, 10, 30, 24)


@pytest.mark.parametrize(
    ("nsec", "expected_seconds", "expected_nsec"),
    [
        (0, 0, 0),
        (_NS_PER_SECOND - 1, 0, _NS_PER_SECOND - 1),
        (_NS_PER_SECOND, 1, 0),
        (_OVERFLOW_NSEC, 1, 232_076_000),
        (_MAX_RAR3_NSEC, 1, _MAX_RAR3_NSEC - _NS_PER_SECOND),
    ],
)
def test_to_nsdatetime_boundaries(
    nsec: int, expected_seconds: int, expected_nsec: int
) -> None:
    """Only a remainder of a second or more carries, and it carries exactly."""
    result = rarfile.to_nsdatetime(_FIXTURE_DTTM, nsec)

    assert result.second == _FIXTURE_DTTM.second + expected_seconds
    assert rarfile.to_nsecs(result) % _NS_PER_SECOND == expected_nsec


def test_to_nsdatetime_carry_rolls_over_the_year() -> None:
    """Carrying a second out of the last second of the year rolls the date."""
    new_years_eve = datetime(2020, 12, 31, 23, 59, 59, tzinfo=UTC)

    result = rarfile.to_nsdatetime(new_years_eve, 1_500_000_000)

    assert result == datetime(2021, 1, 1, 0, 0, 0, 500000, tzinfo=UTC)


def test_patch_does_not_stack() -> None:
    """Patching again leaves the already patched function in place."""
    patched = rarfile.to_nsdatetime

    _patch_nsec_overflow()

    assert rarfile.to_nsdatetime is patched
