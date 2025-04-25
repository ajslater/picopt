"""Data classes."""

from io import BufferedReader, BytesIO
from os import stat_result
from pathlib import Path
from tarfile import TarInfo
from zipfile import ZipInfo

from confuse import AttrDict
from py7zr.py7zr import FileInfo as SevenZipInfo
from rarfile import RarInfo

from picopt.archiveinfo import ArchiveInfo

_CONTAINER_PATH_DELIMETER = ":"
_DOUBLE_SUFFIX = ".tar"
_LOWERCASE_TESTNAME = ".picopt_case_sensitive_test"
_UPPERCASE_TESTNAME = _LOWERCASE_TESTNAME.upper()


def is_path_case_sensitive(dirpath: Path) -> bool:
    """Determine if a path is on a case sensitive filesystem."""
    lowercase_path = dirpath / _LOWERCASE_TESTNAME
    result = False
    try:
        lowercase_path.touch()
        uppercase_path = dirpath / _UPPERCASE_TESTNAME
        result = not uppercase_path.exists()
    finally:
        lowercase_path.unlink(missing_ok=True)
    return result


def is_path_ignored(config: AttrDict, path: str | Path, ignore_case: bool):
    """Match path against the ignore regexp."""
    ignore = config.computed.ignore
    ignore = ignore.ignore_case if ignore_case else ignore.case
    return ignore and bool(ignore.search(str(path)))


class PathInfo:
    """Path Info object, mostly for passing down walk."""

    def __init__(  # noqa: PLR0913
        self,
        top_path: Path,
        convert: bool,
        is_case_sensitive: bool | None,
        path: Path | None = None,
        frame: int | None = None,
        archiveinfo: ZipInfo | RarInfo | TarInfo | SevenZipInfo | None = None,
        data: bytes | None = None,
        container_parents: tuple[str, ...] | None = None,
        in_container: bool = False,  # noqa: FBT002
    ):
        """Initialize."""
        self.top_path: Path = top_path
        self.convert: bool = convert
        self.is_case_sensitive: bool = is_case_sensitive or bool(
            is_case_sensitive is None and is_path_case_sensitive(top_path)
        )

        # A filesystem path
        self.path = path
        # An animated image frame (in a container)
        self.frame = frame
        # An archived file (in a container)
        self.archiveinfo = ArchiveInfo(archiveinfo) if archiveinfo else None
        self.in_container = (
            in_container or self.archiveinfo is not None or self.frame is not None
        )
        # The history of parent container names
        self.container_parents: tuple[str, ...] = (
            container_parents if container_parents else ()
        )

        # optionally computed
        self._data: bytes | None = data

        # always computed
        self._is_dir: bool | None = None
        self._stat: stat_result | bool | None = None
        self._bytes_in: int | None = None
        self._mtime: float | None = None
        self._name: str | None = None
        self._archive_pretty_name: str | None = None
        self._archive_psuedo_path: Path | None = None
        self._suffix: str | None = None
        self._container_path_history: tuple[str, ...] | None = None

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

    def stat(self) -> stat_result | bool:
        """Return fs_stat if possible."""
        if self._stat is None:
            self._stat = self.path.stat() if self.path else False
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

    def set_data(self, data: bytes):
        """Set the data."""
        self._data = data

    def data_clear(self) -> None:
        """Clear the data cache."""
        self._data = None

    def _buffer(self) -> BytesIO:
        """Return a seekable buffer for the data."""
        return BytesIO(self.data())

    def path_or_buffer(self) -> Path | BytesIO:
        """Return a the path or the buffered data."""
        return self.path if self.path else self._buffer()

    def fp_or_buffer(self) -> BufferedReader | BytesIO:
        """Return an file pointer for chunking or buffer."""
        if self.path:
            return self.path.open("rb")
        return self._buffer()

    def bytes_in(self) -> int:
        """Return the length of the data."""
        if self._bytes_in is None:
            stat = self.stat()
            if stat not in (False, True):
                self._bytes_in = stat.st_size
            else:
                self._bytes_in = len(self.data())
        return self._bytes_in

    def mtime(self) -> float:
        """Choose an mtime."""
        if self._mtime is None:
            if self.archiveinfo:
                mtime = self.archiveinfo.mtime()
                if mtime is None:
                    mtime = 0.0
                self._mtime = mtime
            else:
                stat = self.stat()
                if stat and stat is not True:
                    self._mtime = stat.st_mtime
                else:
                    self._mtime = 0.0
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

    def container_path_history(self) -> tuple[str, ...]:
        """Collect container parents plus this path's name."""
        if self._container_path_history is None:
            self._container_path_history = (*self.container_parents, self.name())
        return self._container_path_history

    def full_output_name(self) -> str:
        """Full path string for output."""
        if self._archive_pretty_name is None:
            self._archive_pretty_name = _CONTAINER_PATH_DELIMETER.join(
                self.container_path_history()
            )
        return self._archive_pretty_name

    def archive_psuedo_path(self) -> Path:
        """Return a psudeo path of container history for skipping inside archives."""
        if self._archive_psuedo_path is None:
            path = Path()
            for child in self.container_path_history():
                path = path / child
            self._archive_psuedo_path = path
        return self._archive_psuedo_path

    def suffix(self) -> str:
        """Return file suffix."""
        if self._suffix is None:
            path = Path(self.name())
            suffixes = path.suffixes
            index = -2 if len(suffixes) > 1 and suffixes[-2] == _DOUBLE_SUFFIX else -1
            self._suffix = "".join(suffixes[index:])
        return self._suffix
