"""
Zip-family archive plugin.

Owns: Zip, Cbz, EPub. Uses Python's stdlib zipfile so the "tool" is always
available; the InternalTool here exists purely to participate in the doctor
inventory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, is_zipfile

from typing_extensions import override

from picopt.formats import FileFormat
from picopt.plugins.base import (
    ArchiveHandler,
    Detector,
    Handler,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.tool import StdLibTool
from picopt.plugins.rar import Cbr, Rar
from picopt.plugins.seven_zip import Cb7, SevenZip
from picopt.plugins.tar import Cbt, Tar, TarBz, TarGz, TarXz

if TYPE_CHECKING:
    from io import BytesIO
    from pathlib import Path

    from picopt.path import PathInfo

# ---------------------------------------------------------------------------
# Tool (always-available stdlib zipfile)
# ---------------------------------------------------------------------------


class ZipTool(StdLibTool):
    """The Python stdlib zipfile module. Always present."""

    name = "zipfile"
    module_name = "zipfile"

    @override
    def run_pack(self, handler: Handler) -> BytesIO:
        if not isinstance(handler, Zip):
            msg = "StdlibZipTool only packs Zip handlers"
            raise TypeError(msg)
        return ArchiveHandler.pack_into(handler)


_ZIP_TOOL = ZipTool()


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


class ZipDetector(Detector):
    """Detect zip-family archives via suffix + magic bytes."""

    PRIORITY: int = 10

    @override
    @classmethod
    def identify(cls, path_info: PathInfo) -> FileFormat | None:
        suffix = path_info.suffix().lower()
        if suffix not in _SUFFIX_TO_FORMAT:
            return None
        if not is_zipfile(path_info.path_or_buffer()):
            return None
        return _SUFFIX_TO_FORMAT[suffix]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class Zip(ArchiveHandler):
    """Zip container."""

    OUTPUT_FORMAT_STR: str = "ZIP"
    SUFFIXES: tuple[str, ...] = (".zip",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    ARCHIVE_CLASS = ZipFile
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((_ZIP_TOOL,),)

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        return is_zipfile(path)

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.infolist()

    @override
    def _archive_readfile(self, archive, archiveinfo):
        return archive.read(archiveinfo.filename)

    @override
    def _set_comment(self, archive) -> None:
        if archive.comment:
            self.comment = archive.comment

    @override
    def _archive_for_write(self, output_buffer: BytesIO) -> ZipFile:
        return ZipFile(output_buffer, "x", compression=ZIP_DEFLATED, compresslevel=9)

    @override
    def _pack_info_one_file(self, archive, path_info) -> None:
        zipinfo = path_info.archiveinfo.to_zipinfo()
        if not self.config.keep_metadata and (
            not zipinfo.compress_type or zipinfo.compress_type == ZIP_STORED
        ):
            zipinfo.compress_type = ZIP_DEFLATED
        archive.writestr(zipinfo, path_info.data())


class Cbz(Zip):
    """CBZ comic-book archive."""

    OUTPUT_FORMAT_STR: str = "CBZ"
    SUFFIXES: tuple[str, ...] = (".cbz",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


class EPub(Zip):
    """EPub archive (zip with mandatory layout)."""

    OUTPUT_FORMAT_STR: str = "EPUB"
    SUFFIXES: tuple[str, ...] = (".epub",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    # Internal links would break if we converted images to a different format.
    CONVERT_CHILDREN: bool = False


_SUFFIX_TO_FORMAT: dict[str, FileFormat] = {
    ".zip": Zip.OUTPUT_FILE_FORMAT,
    ".cbz": Cbz.OUTPUT_FILE_FORMAT,
    ".epub": EPub.OUTPUT_FILE_FORMAT,
}


PLUGIN = Plugin(
    name="ZIP",
    handlers=(Zip, Cbz, EPub),
    routes=(
        Route(file_format=Zip.OUTPUT_FILE_FORMAT, native=Zip),
        Route(file_format=Cbz.OUTPUT_FILE_FORMAT, native=Cbz),
        Route(file_format=EPub.OUTPUT_FILE_FORMAT, native=EPub),
        # Rar
        Route(file_format=Rar.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=Cbr.OUTPUT_FILE_FORMAT, convert=(Cbz,)),
        # Tar
        Route(file_format=Tar.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=TarGz.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=TarBz.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=TarXz.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=Cbt.OUTPUT_FILE_FORMAT, convert=(Cbz,)),
        # SevenZip
        Route(file_format=SevenZip.OUTPUT_FILE_FORMAT, convert=(Zip,)),
        Route(file_format=Cb7.OUTPUT_FILE_FORMAT, convert=(Cbz,)),
    ),
    convert_targets=(Zip, Cbz),
    detector=ZipDetector,
    default_enabled=False,
)
