"""
RAR-family archive plugin.

Owns: Rar, Cbr. RAR is read-only because the format is non-free; the unrar
binary is read-only by design. The plugin sets ``CAN_PACK = False`` and the
routing layer will only enable RAR if a convert target (Zip or Cbz) is
configured.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import wraps
from importlib.resources import as_file, files
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import rarfile
from rarfile import RarFile, is_rarfile
from typing_extensions import override

from picopt.plugins.base import (
    ArchiveHandler,
    Detector,
    ExternalTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat

if TYPE_CHECKING:
    from io import BytesIO
    from pathlib import Path

    from picopt.path import PathInfo
    from picopt.plugins.base.tool import ToolStatus


# ---------------------------------------------------------------------------
# rarfile patch: sub-second timestamp overflow
# ---------------------------------------------------------------------------

_NS_PER_SECOND: Final = 1_000_000_000
_PROBE_DATETIME: Final = datetime(2020, 1, 1, tzinfo=UTC)
# Any remainder of a second or more trips the bug. The value is arbitrary.
_PROBE_NSEC: Final = 1_500_000_000


def _is_nsec_overflow_broken() -> bool:
    """Report whether rarfile still crashes on an overlong remainder."""
    try:
        rarfile.to_nsdatetime(_PROBE_DATETIME, _PROBE_NSEC)
    except ValueError:
        return True
    return False


def _patch_nsec_overflow() -> None:
    """
    Carry whole seconds out of rarfile's to_nsdatetime nanosecond argument.

    rarfile <= 4.5 raises ``ValueError: microsecond must be in 0..999999``
    from ``RarFile.__init__`` when a RAR3 extended timestamp carries a
    sub-second remainder of one second or more, which some third-party
    packers write. Its ``_parse_xtime`` builds the remainder from three bytes
    (up to 1.68 seconds in 100ns units) and hands it to ``to_nsdatetime``
    unclamped, so the archive can't be opened at all.

    Probing behavior instead of marking the module makes this a no-op both
    when already patched and when a future rarfile fixes the bug.
    """
    if not _is_nsec_overflow_broken():
        return
    original = rarfile.to_nsdatetime

    @wraps(original)
    def to_nsdatetime(dttm: datetime, nsec: int) -> datetime:
        if nsec >= _NS_PER_SECOND:
            extra_seconds, nsec = divmod(nsec, _NS_PER_SECOND)
            dttm += timedelta(seconds=extra_seconds)
        return original(dttm, nsec)

    # Rebinding a module function is valid at run time, but ty types each
    # def as its own function and accepts no other in its place.
    rarfile.to_nsdatetime = to_nsdatetime  # ty: ignore[invalid-assignment]


# Every process that opens a RAR imports this module first: workers do so to
# unpickle the handler. The import lock keeps concurrent imports from
# stacking wrappers.
_patch_nsec_overflow()


# ---------------------------------------------------------------------------
# Tool: the unrar binary that python-rarfile shells out to
# ---------------------------------------------------------------------------


# A RAR5 archive holding one compressed member: comicbox's probe fixture,
# made with ``rar a -ma5 -m5 -ep _rar_probe.rar probe.txt`` from 64 copies of
# the line "comicbox rar probe". It must stay compressed: rarfile reads stored
# members itself, so a stored probe would pass with no tool installed.
_PROBE_ARCHIVE: Final = "_rar_probe.rar"
_PROBE_MEMBER: Final = "probe.txt"


def _rarfile_tool_name() -> str:
    """
    Name the tool rarfile picked, or "" if that can't be read.

    rarfile caches the first tool whose check command passes, so an unrar
    that fails its check is silently replaced by unar, 7z or bsdtar.
    ``CURRENT_SETUP`` is undocumented, so any failure only drops the name.
    """
    try:
        current_setup: Any = getattr(rarfile, "CURRENT_SETUP", None)
        setup_key = current_setup.setup["open_cmd"][0]
        return str(getattr(rarfile, setup_key, setup_key))
    except Exception:
        return ""


def rar_extract_error() -> str:
    """Why rarfile can't extract a compressed RAR5 member, or "" if it can."""
    probe = files("picopt.plugins") / _PROBE_ARCHIVE
    try:
        # The external tool needs a real file, not a package resource.
        with as_file(probe) as probe_path, RarFile(probe_path) as archive:
            archive.read(_PROBE_MEMBER)
    except (rarfile.Error, OSError) as exc:
        return f"cannot extract RAR5: {type(exc).__name__}: {exc}"
    return ""


class UnrarTool(ExternalTool):
    """
    The ``unrar`` binary used by python-rarfile.

    Finding ``unrar`` on PATH proves little: another build may answer to
    that name, and rarfile swaps in another tool when unrar fails its
    check. So the probe extracts a real compressed member through rarfile,
    which tests whichever backend a run will actually use.
    """

    name = "unrar"
    binary = "unrar"
    version_line = 1
    version_args = ()

    @override
    def parse_version(self, version: str) -> str:
        """Parse unrar version."""
        # this looks fragile. Tuned to unrar 7.11 beta 1.
        # NOTE: unrar prints its version banner without --version (it just
        # prints help). We accept that.
        version = super().parse_version(version)
        return " ".join(version.split()[1:-6])

    @override
    def _probe(self) -> ToolStatus:
        status = super()._probe()
        if not status.available:
            return status
        if error := rar_extract_error():
            return replace(status, available=False, error=error)
        detail = "extracts RAR5"
        tool_name = _rarfile_tool_name()
        if tool_name and tool_name != rarfile.UNRAR_TOOL:
            detail += f" via {tool_name}"
        return replace(status, detail=detail)


_UNRAR_TOOL = UnrarTool()


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class RarDetector(Detector):
    """Detect rar-family archives."""

    PRIORITY: int = 10

    @override
    @classmethod
    def identify(cls, path_info: PathInfo) -> FileFormat | None:
        suffix = path_info.suffix().lower()
        if suffix not in _SUFFIX_TO_FORMAT:
            return None
        if not is_rarfile(path_info.path_or_buffer()):
            return None
        return _SUFFIX_TO_FORMAT[suffix]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class Rar(ArchiveHandler):
    """
    RAR container.

    Read-only: RAR can be unpacked but not repacked, so it always converts
    to Zip.
    """

    OUTPUT_FORMAT_STR: str = "RAR"
    SUFFIXES: tuple[str, ...] = (".rar",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    ARCHIVE_CLASS = RarFile
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((_UNRAR_TOOL,),)
    CAN_PACK: bool = False

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_rarfile(path)

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.infolist()

    @override
    def _archive_readfile(self, archive, archiveinfo) -> bytes:
        if archiveinfo.is_dir():
            return b""
        return archive.read(archiveinfo.filename)

    @override
    def _set_comment(self, archive: RarFile) -> None:
        if archive.comment:
            self.comment = archive.comment.encode()


class Cbr(Rar):
    """CBR comic-book archive."""

    OUTPUT_FORMAT_STR: str = "CBR"
    SUFFIXES: tuple[str, ...] = (".cbr",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


_SUFFIX_TO_FORMAT: MappingProxyType[str, FileFormat] = MappingProxyType(
    {
        ".rar": Rar.OUTPUT_FILE_FORMAT,
        ".cbr": Cbr.OUTPUT_FILE_FORMAT,
    }
)


PLUGIN = Plugin(
    name="RAR",
    handlers=(Rar, Cbr),
    routes=(
        # Native: yes (we can read it). Convert: required (we can't write it).
        Route(file_format=Rar.OUTPUT_FILE_FORMAT, native=Rar),
        Route(file_format=Cbr.OUTPUT_FILE_FORMAT, native=Cbr),
    ),
    detector=RarDetector,
    default_enabled=False,
    input_only=True,
)
