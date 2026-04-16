"""
RAR-family archive plugin.

Owns: Rar, Cbr. RAR is read-only because the format is non-free; the unrar
binary is read-only by design. The plugin sets ``CAN_PACK = False`` and the
routing layer will only enable RAR if a convert target (Zip or Cbz) is
configured.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from rarfile import RarFile, is_rarfile
from typing_extensions import override

from picopt.plugins.base import (
    ArchiveHandler,
    Detector,
    ExternalTool,
    Plugin,
    Route,
    Tool,
    ToolStatus,
)
from picopt.plugins.base.format import FileFormat

if TYPE_CHECKING:
    from io import BytesIO
    from pathlib import Path

    from picopt.path import PathInfo


# ---------------------------------------------------------------------------
# Tool: the unrar binary that python-rarfile shells out to
# ---------------------------------------------------------------------------


class UnrarTool(ExternalTool):
    """The ``unrar`` binary used by python-rarfile."""

    name = "unrar"
    binary = "unrar"
    version_line = 1
    version_args = ()

    @override
    def parse_version(self: UnrarTool, version: str) -> str:
        """Parse unrar version."""
        # this looks fragile. Tuned to unrar 7.11 beta 1.
        version = super().parse_version(version)
        return " ".join(version.split()[1:-6])

    @override
    def probe(self: UnrarTool) -> ToolStatus:
        # Default ExternalTool.probe is fine, but unrar prints its version
        # banner without --version (it just prints help). We accept that.
        return super().probe()


_UNRAR_TOOL = UnrarTool()


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class RarDetector(Detector):
    """Detect rar-family archives."""

    PRIORITY: int = 10

    @override
    @classmethod
    def identify(cls: type[Any], path_info: PathInfo) -> FileFormat | None:
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
