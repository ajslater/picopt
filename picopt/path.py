"""Data classes."""
from collections.abc import Sequence
from datetime import datetime, timezone
from io import BufferedReader, BytesIO
from os import stat_result
from pathlib import Path
from zipfile import ZipInfo

from confuse import AttrDict

TMP_DIR = Path("__picopt_tmp")
CONTAINER_PATH_DELIMETER = " - "


class PathInfo:
    """Path Info object, mostly for passing down walk."""

    def __init__(  # noqa: PLR0913
        self,
        top_path: Path,
        container_mtime: float,
        convert: bool,
        is_case_sensitive: bool,
        path: Path | None = None,
        frame: int | None = None,
        zipinfo: ZipInfo | None = None,
        data: bytes | None = None,
        container_paths: Sequence[str] | None = None,
    ):
        """Initialize."""
        self.top_path: Path = top_path
        self.container_mtime: float = container_mtime
        self.convert: bool = convert
        self.is_case_sensitive: bool = is_case_sensitive

        # type
        # A filesystem path
        self.path: Path | None = path
        # An animated image frame (in a container)
        self.frame: int | None = frame
        # An archived file (in a container)
        self.zipinfo: ZipInfo | None = zipinfo
        # The history of parent container names
        self.container_paths: tuple[str, ...] = (
            tuple(container_paths) if container_paths else ()
        )

        # optionally computed
        self._data: bytes | None = data

        # always computed
        self._is_dir: bool | None = None
        self._stat: stat_result | bool | None = None
        self._bytes_in: int | None = None
        self._mtime: float | None = None
        self._name: str | None = None
        self._full_name: str | None = None
        self._suffix: str | None = None
        self._is_container_child: bool | None = None

    def is_dir(self) -> bool:
        """Is the file a directory."""
        if self._is_dir is None:
            if self.zipinfo:
                self._is_dir = self.zipinfo.is_dir()
            elif self.path:
                self._is_dir = self.path.is_dir()
            else:
                self._is_dir = False

        return self._is_dir

    def is_container_child(self) -> bool:
        """Is this path inside a container."""
        if self._is_container_child is None:
            self._is_container_child = self.frame is not None or bool(
                self.container_mtime
            )
        return self._is_container_child

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
            if self.zipinfo:
                self._mtime = datetime(
                    *self.zipinfo.date_time, tzinfo=timezone.utc
                ).timestamp()
            elif self.container_mtime:
                self._mtime = self.container_mtime
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
            if self.path:
                self._name = str(self.path)
            elif self.frame:
                self._name = f"frame_#{self.frame:03d}.img"
            elif self.zipinfo:
                self._name = self.zipinfo.filename
            else:
                self._name = "Unknown"
        return self._name

    def full_name(self) -> str:
        """Full name."""
        if self._full_name is None:
            self._full_name = CONTAINER_PATH_DELIMETER.join(
                (*self.container_paths, self.name())
            )
        return self._full_name

    def suffix(self) -> str:
        """Return file suffix."""
        if self._suffix is None:
            self._suffix = Path(self.name()).suffix
        return self._suffix


def is_path_ignored(config: AttrDict, path: Path):
    """Match path against the ignore list."""
    return any(path.match(ignore_glob) for ignore_glob in config.ignore)
