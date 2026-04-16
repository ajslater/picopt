"""
Tar-family archive plugin.

Owns: Tar, TarGz, TarBz, TarXz, Cbt. Uses Python's stdlib :mod:`tarfile`
for both reading and writing; the InternalTool here exists only for the
doctor inventory.

Detector ordering matters: ``is_tarfile()`` matches plain tar *and*
gzipped/bzipped/xzipped tar (Python's tarfile transparently
decompresses), so the compressed-variant detectors set ``PRIORITY = 20``
to run before plain :class:`Tar` (``PRIORITY = 10``). This puts the
ordering constraint next to the classes that need it instead of in a
hand-maintained list inside the dispatcher.
"""

from __future__ import annotations

from io import BytesIO
from tarfile import TarFile, TarInfo, is_tarfile
from tarfile import open as tar_open
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import filetype
from typing_extensions import override

from picopt.plugins.base import (
    ArchiveHandler,
    Detector,
    Handler,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat
from picopt.plugins.base.tool import StdLibTool

if TYPE_CHECKING:
    from pathlib import Path

    from picopt.path import PathInfo


# ---------------------------------------------------------------------------
# Tool (always-available stdlib tarfile)
# ---------------------------------------------------------------------------


class TarTool(StdLibTool):
    """The Python stdlib :mod:`tarfile` module. Always present."""

    name = "tarfile"
    module_name = "tarfile"

    @override
    def run_pack(self, handler: Handler) -> BytesIO:
        if not isinstance(handler, Tar):
            msg = "StdlibTarTool only packs Tar handlers"
            raise TypeError(msg)
        return ArchiveHandler.pack_into(handler)


_TAR_TOOL = TarTool()


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


class _TarBaseDetector(Detector):
    """Shared sniff logic: suffix lookup → ``is_tarfile`` → optional MIME."""

    PRIORITY: int = 10
    SUFFIX_MAP: MappingProxyType[str, FileFormat] = MappingProxyType({})
    COMPRESSION_MIME: str = ""

    @override
    @classmethod
    def identify(cls: type[TarGzDetector], path_info: PathInfo) -> FileFormat | None:
        suffix = path_info.suffix().lower()
        if suffix not in cls.SUFFIX_MAP:
            return None
        target = path_info.path_or_buffer()
        if not is_tarfile(target):
            return None
        if cls.COMPRESSION_MIME:
            ft = filetype.guess(target)
            if not ft or ft.mime != cls.COMPRESSION_MIME:
                return None
        return cls.SUFFIX_MAP[suffix]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class Tar(ArchiveHandler):
    """Plain (uncompressed) tarball."""

    OUTPUT_FORMAT_STR: str = "TAR"
    SUFFIXES: tuple[str, ...] = (".tar",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    ARCHIVE_CLASS = TarFile
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((_TAR_TOOL,),)

    WRITE_MODE: str = "w"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})

    @override
    @classmethod
    def _is_archive(cls, path: Path | BytesIO) -> bool:
        # The detector is the gatekeeper for compressed-vs-plain
        # disambiguation; here we only need to confirm it's tarfile-readable.
        return is_tarfile(path)

    @override
    def _get_archive(self) -> TarFile:
        archive = tar_open(self.original_path, "r")  # noqa: SIM115
        if not archive:
            msg = f"Unknown archive type: {self.original_path}"
            raise ValueError(msg)
        return archive

    @override
    @staticmethod
    def _archive_infolist(archive):
        return archive.getmembers()

    @override
    def _archive_readfile(self, archive, archiveinfo) -> bytes:
        if buf := archive.extractfile(archiveinfo):
            return buf.read()
        return b""

    @override
    def _set_comment(self, archive: TarFile) -> None:
        """Tar has no archive-level comment."""

    @override
    def _archive_for_write(self, output_buffer: BytesIO) -> TarFile:
        return tar_open(  # pyright: ignore[reportCallIssue], # ty: ignore[no-matching-overload]
            mode=self.WRITE_MODE,  # pyright: ignore[reportArgumentType]
            fileobj=output_buffer,
            **self.COMPRESS_KWARGS,
        )

    @override
    def _pack_info_one_file(self, archive, path_info) -> None:
        tarinfo: TarInfo = path_info.archiveinfo.to_tarinfo()
        data = path_info.data()
        tarinfo.size = len(data)
        archive.addfile(tarinfo, BytesIO(data))


class TarGz(Tar):
    """Gzip-compressed tarball."""

    OUTPUT_FORMAT_STR: str = "TGZ"
    SUFFIXES: tuple[str, ...] = (".tar.gz", ".tgz")
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    WRITE_MODE: str = "w:gz"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"compresslevel": 9})


class TarBz(Tar):
    """Bzip2-compressed tarball."""

    OUTPUT_FORMAT_STR: str = "TBZ"
    SUFFIXES: tuple[str, ...] = (".tar.bz2", ".tbz")
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    WRITE_MODE: str = "w:bz2"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"compresslevel": 9})


class TarXz(Tar):
    """LZMA/xz-compressed tarball."""

    OUTPUT_FORMAT_STR: str = "TXZ"
    SUFFIXES: tuple[str, ...] = (".tar.xz", ".txz")
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    WRITE_MODE: str = "w:xz"
    COMPRESS_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"preset": 9})


class Cbt(Tar):
    """CBT comic-book tar archive (uncompressed)."""

    OUTPUT_FORMAT_STR: str = "CBT"
    SUFFIXES: tuple[str, ...] = (".cbt",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})


# ---------------------------------------------------------------------------
# Detector wiring (must come after handler classes for the suffix maps)
# ---------------------------------------------------------------------------


class TarGzDetector(_TarBaseDetector):
    """``.tar.gz`` / ``.tgz``."""

    PRIORITY: int = 20
    SUFFIX_MAP = MappingProxyType(
        {".tar.gz": TarGz.OUTPUT_FILE_FORMAT, ".tgz": TarGz.OUTPUT_FILE_FORMAT}
    )
    COMPRESSION_MIME: str = "application/gzip"


class TarBzDetector(_TarBaseDetector):
    """``.tar.bz2`` / ``.tbz``."""

    PRIORITY: int = 20
    SUFFIX_MAP = MappingProxyType(
        {".tar.bz2": TarBz.OUTPUT_FILE_FORMAT, ".tbz": TarBz.OUTPUT_FILE_FORMAT}
    )
    COMPRESSION_MIME: str = "application/x-bzip2"


class TarXzDetector(_TarBaseDetector):
    """``.tar.xz`` / ``.txz``."""

    PRIORITY: int = 20
    SUFFIX_MAP = MappingProxyType(
        {".tar.xz": TarXz.OUTPUT_FILE_FORMAT, ".txz": TarXz.OUTPUT_FILE_FORMAT}
    )
    COMPRESSION_MIME: str = "application/x-xz"


class TarDetector(_TarBaseDetector):
    """
    Plain ``.tar`` and ``.cbt``.

    Lower priority than the compressed variants so a ``.tar.gz`` file is
    matched as gz first; ``.cbt`` and plain ``.tar`` only reach this
    detector after the compressed checks have all returned None.
    """

    PRIORITY: int = 10
    SUFFIX_MAP = MappingProxyType(
        {
            ".tar": Tar.OUTPUT_FILE_FORMAT,
            ".cbt": Cbt.OUTPUT_FILE_FORMAT,
        }
    )


# The plugin descriptor takes one ``detector`` slot but tar needs four.
# Wrap them all in a single classmethod that delegates by priority order.
class _TarFamilyDetector(Detector):
    """
    Composite detector that runs every tar variant in priority order.

    The plugin descriptor only carries one detector per plugin; the
    registry sorts detectors across plugins by ``PRIORITY``. To respect
    the within-tar ordering constraint we expose this composite that
    walks the four real detectors in priority order on each call.
    """

    PRIORITY: int = 20  # at least as high as the highest member

    _MEMBERS: tuple[type[Detector], ...] = (
        TarGzDetector,
        TarBzDetector,
        TarXzDetector,
        TarDetector,
    )

    @override
    @classmethod
    def identify(
        cls: type[_TarFamilyDetector], path_info: PathInfo
    ) -> FileFormat | None:
        for member in cls._MEMBERS:
            if (fmt := member.identify(path_info)) is not None:
                return fmt
        return None


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------


PLUGIN = Plugin(
    name="TAR",
    handlers=(Tar, TarGz, TarBz, TarXz, Cbt),
    routes=(
        Route(file_format=Tar.OUTPUT_FILE_FORMAT, native=Tar),
        Route(file_format=TarGz.OUTPUT_FILE_FORMAT, native=TarGz),
        Route(file_format=TarBz.OUTPUT_FILE_FORMAT, native=TarBz),
        Route(file_format=TarXz.OUTPUT_FILE_FORMAT, native=TarXz),
        Route(file_format=Cbt.OUTPUT_FILE_FORMAT, native=Cbt),
    ),
    detector=_TarFamilyDetector,
    default_enabled=False,
)
