"""Data classes."""

from io import BufferedReader, BytesIO
from os import stat_result
from pathlib import Path
from tarfile import TarInfo
from typing import cast
from zipfile import ZipInfo

from py7zr.py7zr import FileInfo as SevenZipInfo
from rarfile import RarInfo

from picopt.archiveinfo import ArchiveInfo
from picopt.config.settings import PicoptSettings

_CONTAINER_PATH_DELIMITER = ":"
_LOWERCASE_TESTNAME = ".picopt_case_sensitive_test"
_UPPERCASE_TESTNAME: str = _LOWERCASE_TESTNAME.upper()
# Special case only supported double suffixes prevents heaps of false signals for
# other multiple suffix types.
DOUBLE_SUFFIX = ".tar"
# Bytes cached for header_bytes(). Sized to cover the largest magic-byte
# window any current detector needs (PDF: 1024) with margin.
_HEADER_BYTES_CACHE_SIZE = 4096


def is_path_case_sensitive(dirpath: Path) -> bool:
    """Determine if a path is on a case sensitive filesystem."""
    lowercase_path = dirpath / _LOWERCASE_TESTNAME
    try:
        lowercase_path.touch()
        uppercase_path = dirpath / _UPPERCASE_TESTNAME
        result = not uppercase_path.exists()
    finally:
        lowercase_path.unlink(missing_ok=True)
    return result


def is_path_ignored(config: PicoptSettings, path: Path, *, ignore_case: bool) -> bool:
    """Match path against the ignore regexp."""
    patterns = config.computed.ignore
    ignore = patterns.ignore_case if ignore_case else patterns.case
    return ignore is not None and bool(ignore.search(str(path)))


class PathInfo:
    """Path Info object, mostly for passing down walk."""

    _UNSET = object()

    def _copy_constructor(
        self,
        path_info: "PathInfo | None" = None,
        top_path: Path | None = None,
        container_parents: tuple[str, ...] | None = None,
        *,
        convert: bool | None = None,
        is_case_sensitive: bool | None = None,
        noop: bool = False,
    ) -> None:
        """Copy from path_info or override with arg."""

        def pick(override: object, attr: str, default: object = self._UNSET) -> object:
            """Resolve a field: explicit override > path_info > default > raise."""
            if override is not None:
                return override
            if path_info is not None:
                return getattr(path_info, attr)
            if default is self._UNSET:
                msg = f"PathInfo requires a {attr} argument."
                raise ValueError(msg)
            return default() if callable(default) else default  # ty: ignore[call-top-callable]

        self.top_path: Path = cast("Path", pick(top_path, "top_path"))
        self.convert: bool = cast("bool", pick(convert, "convert"))
        self.is_case_sensitive: bool = cast(
            "bool",
            pick(
                is_case_sensitive,
                "is_case_sensitive",
                default=lambda: is_path_case_sensitive(self.top_path),
            ),
        )
        self.container_parents: tuple[str, ...] = cast(
            "tuple[str, ...]",
            pick(container_parents, "container_parents", default=()),
        )
        self.noop = noop

    def __init__(  # noqa: PLR0913
        self,
        path_info: "PathInfo | None" = None,
        *,
        top_path: Path | None = None,
        convert: bool | None = None,
        is_case_sensitive: bool | None = None,
        container_parents: tuple[str, ...] | None = None,
        path: Path | None = None,
        frame: int | None = None,
        archiveinfo: ZipInfo | RarInfo | TarInfo | SevenZipInfo | None = None,
        data: bytes | None = None,
        noop: bool = False,
    ) -> None:
        """Initialize."""
        self._copy_constructor(
            path_info,
            top_path,
            container_parents,
            convert=convert,
            is_case_sensitive=is_case_sensitive,
            noop=noop,
        )

        ###############
        # Primary key #
        ###############
        # A filesystem path
        self.path: Path | None = path
        # An animated image frame (in a container)
        self.frame: int | None = frame
        # An archived file (in a container)
        self.archiveinfo: ArchiveInfo | None = (
            ArchiveInfo(archiveinfo) if archiveinfo else None
        )

        # optionally computed
        self._data: bytes | None = data
        self._header_bytes: bytes | None = None

        # always computed
        self._is_dir: bool | None = None
        self._stat: stat_result | None = None
        self._stat_cached: bool = False
        self._bytes_in: int | None = None
        self._mtime: float | None = None
        self._name: str | None = None
        self._archive_pretty_name: str | None = None
        self._archive_pseudo_path: Path | None = None
        self._suffix: str | None = None
        self._container_path_history: tuple[str, ...] | None = None
        self.original_name: str = self.name()

    def is_dir(self) -> bool:
        """Is the file a directory."""
        if self._is_dir is None:
            if self.archiveinfo:
                self._is_dir = self.archiveinfo.is_dir()
            elif self.path:
                self._is_dir = self.path.is_dir()
            else:
                self._is_dir = False

        return self._is_dir

    def stat(self) -> stat_result | None:
        """Return fs_stat if possible."""
        if not self._stat_cached:
            self._stat = self.path.stat() if self.path else None
            self._stat_cached = True
        return self._stat

    def data(self) -> bytes:
        """Get the data from the file."""
        if self._data is None:
            if not self.path or self.path.is_dir():
                self._data = b""
            else:
                with self.path.open("rb") as fp:
                    self._data = fp.read()
        return self._data

    def set_data(self, data: bytes) -> None:
        """Set the data."""
        self._data = data

    def header_bytes(self) -> bytes:
        """First _HEADER_BYTES_CACHE_SIZE bytes of the file, cached for detectors."""
        if self._header_bytes is None:
            if self._data is not None:
                self._header_bytes = self._data[:_HEADER_BYTES_CACHE_SIZE]
            elif self.path and not self.path.is_dir():
                try:
                    with self.path.open("rb") as fp:
                        self._header_bytes = fp.read(_HEADER_BYTES_CACHE_SIZE)
                except OSError:
                    self._header_bytes = b""
            else:
                self._header_bytes = b""
        return self._header_bytes

    def _buffer(self) -> BytesIO:
        """Return a seekable buffer for the data."""
        return BytesIO(self.data())

    def path_or_buffer(self) -> Path | BytesIO:
        """Return a the path or the buffered data."""
        return self.path or self._buffer()

    def fp_or_buffer(self) -> BufferedReader | BytesIO:
        """Return an file pointer for chunking or buffer."""
        if self.path:
            return self.path.open("rb")
        return self._buffer()

    def bytes_in(self) -> int:
        """Return the length of the data."""
        if self._bytes_in is None:
            stat = self.stat()
            if stat is None:
                self._bytes_in = len(self.data())
            else:
                self._bytes_in = stat.st_size
        return self._bytes_in

    def mtime(self) -> float:
        """Choose an mtime."""
        if self._mtime is None:
            if self.archiveinfo:
                self._mtime = self.archiveinfo.mtime() or 0.0
            else:
                stat = self.stat()
                self._mtime = stat.st_mtime if stat is not None else 0.0
        return self._mtime

    def name(self) -> str:
        """Name."""
        if self._name is None:
            if self.archiveinfo:
                self._name = self.archiveinfo.filename()
            elif self.path:
                self._name = str(self.path)
            elif self.frame:
                self._name = f"frame_#{self.frame:03d}.img"
            else:
                self._name = "Unknown"
        return self._name

    def rename(self, filename: str | Path) -> None:
        """Rename file."""
        if self.path:
            self.path = Path(filename)
        if self.archiveinfo:
            self.archiveinfo.rename(filename)

        # Clear caches that use _name
        self._name = self._suffix = self._container_path_history = None
        self._archive_pretty_name = self._archive_pseudo_path = None

    def container_path_history(self) -> tuple[str, ...]:
        """Collect container parents plus this path's name."""
        if self._container_path_history is None:
            self._container_path_history = (*self.container_parents, self.name())
        return self._container_path_history

    def full_output_name(self) -> str:
        """Full path string for output."""
        if self._archive_pretty_name is None:
            self._archive_pretty_name = _CONTAINER_PATH_DELIMITER.join(
                self.container_path_history()
            )
        return self._archive_pretty_name

    def archive_pseudo_path(self) -> Path:
        """Return a pseudeo path of container history for skipping inside archives."""
        if self._archive_pseudo_path is None:
            path = Path()
            for child in self.container_path_history():
                path = path / child
            self._archive_pseudo_path = path
        return self._archive_pseudo_path

    def suffix(self) -> str:
        """Return first suffix or tar+ suffix."""
        if self._suffix is None:
            path = Path(self.name())
            suffixes = path.suffixes
            index = -2 if len(suffixes) > 1 and suffixes[-2] == DOUBLE_SUFFIX else -1
            self._suffix = "".join(suffixes[index:])
        return self._suffix
