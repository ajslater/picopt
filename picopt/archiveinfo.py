"""Archive Info Converter."""

from typing import TYPE_CHECKING, Final, TypeAlias

if TYPE_CHECKING:
    import picopt.path

from datetime import datetime, timezone
from operator import attrgetter
from pathlib import Path
from tarfile import DIRTYPE, REGTYPE, SYMTYPE, TarInfo
from zipfile import ZipInfo

from py7zr import FileInfo as SevenZipInfo
from py7zr.py7zr import FileInfo
from rarfile import RarInfo

_DATETIME_ATTRGETTER = attrgetter(
    "year", "month", "day", "hour", "minute", "second", "microsecond"
)
ArchiveInfoType: TypeAlias = TarInfo | RarInfo | ZipInfo | SevenZipInfo


class SevenZipInfoDefaults:
    """Defaults for SevenZip FileInfo."""

    compressed: Final[bool] = True
    uncompressed: Final[bool] = False
    archivable: Final[bool] = True
    crc32: Final[None] = None


class ArchiveInfo:
    """Archive Info Converter."""

    def __init__(self, info: ArchiveInfoType) -> None:
        """Store the source info."""
        self.info: ArchiveInfoType = info
        self._filename: str | None = None
        self._is_dir: bool | None = None
        self._mtime: float | None = None
        self._dttm: datetime | None = None
        if isinstance(self.info, RarInfo):
            # This weird hack because
            # Some instances of RarInfo don't serialize properly for multiprocessing
            self.info = self.to_zipinfo()

    def filename(self):
        """Return archive filename."""
        if self._filename is None:
            match self.info:
                case TarInfo():
                    self._filename = self.info.name or ""
                case _:  # ZipInfo | SevenZipInfo | RarInfo
                    self._filename = self.info.filename or ""
        return self._filename

    def rename(self: "picopt.path.ArchiveInfo", filename: str | Path) -> None:
        """Rename archiveinfo."""
        filename = str(filename)
        match self.info:
            case ZipInfo() | SevenZipInfo():
                self.info.filename = filename
            case TarInfo():
                self.info.name = filename
            case _:
                msg = f"{self.info} cannot be renamed."
                raise TypeError(msg)

        # clear filename cache
        self._filename = None

    def is_dir(self) -> bool:
        """Is a directory."""
        if self._is_dir is None:
            match self.info:
                case ZipInfo() | RarInfo():
                    self._is_dir = self.info.is_dir()
                case TarInfo():
                    self._is_dir = self.info.isdir()
                case SevenZipInfo():
                    self._is_dir = bool(self.info.is_directory)
        return self._is_dir  # ty: ignore[invalid-return-type]

    def datetime(self: "picopt.path.ArchiveInfo") -> datetime | None:
        """Return mtime as a datetime."""
        if self._dttm is None:
            dttm: datetime | None = None
            match self.info:
                case ZipInfo():
                    if date_time := self.info.date_time:
                        dttm = datetime(*date_time)  # noqa: DTZ001
                case TarInfo():
                    dttm = datetime.fromtimestamp(self.info.mtime, tz=timezone.utc)
                case SevenZipInfo():
                    dttm = self.info.creationtime
                case _:  # RarInfo
                    dttm = self.info.mtime or None

            if dttm:
                if not dttm.tzinfo:
                    dttm = dttm.replace(tzinfo=timezone.utc)
                self._dttm = dttm
        return self._dttm

    def mtime(self: "picopt.path.ArchiveInfo") -> float | None:
        """Return Modified Timestamp."""
        if self._mtime is None:
            match self.info:
                case TarInfo():
                    self._mtime = self.info.mtime
                case _:  # SevenZipInfo | ZipInfo | RarInfo
                    dttm = self.datetime()
                    if dttm is not None:
                        self._mtime = dttm.timestamp()
        return self._mtime

    def to_zipinfo(self) -> ZipInfo:
        """Convert to ZipInfo."""
        match self.info:
            case ZipInfo():
                info = self.info
            case RarInfo():
                kwargs = {}
                if filename := self.filename():
                    kwargs["filename"] = filename
                if self.info.date_time:
                    kwargs["date_time"] = self.info.date_time
                info = ZipInfo(**kwargs)
            case _:  # TarInfo | SevenZipInfo
                date_time = _DATETIME_ATTRGETTER(self.datetime())
                info = ZipInfo(filename=self.filename(), date_time=date_time)
        return info

    def to_tarinfo(self) -> TarInfo:
        """Convert to TarInfo."""
        match self.info:
            case TarInfo():
                return self.info
            case ZipInfo() | RarInfo():
                kwargs = {}
                if name := self.filename():
                    kwargs["name"] = name
            case _:  # SevenZipInfo
                kwargs = {"name": self.info.filename}
        info = TarInfo(**kwargs)
        mtime = self.mtime()
        if mtime is not None:
            info.mtime = mtime
        return info

    def to_sevenzipinfo(self) -> FileInfo:
        """Convert to SevenZip FileInfo."""
        if isinstance(self.info, SevenZipInfo):
            return self.info

        match self.info:
            case ZipInfo():
                filename = self.info.filename
                is_dir = self.info.is_dir()
                # X is_file = self.info.is_file() # python 3.11?
                is_file = not is_dir
                # X is_symlink = self.info.is_symlink() # python 3.13
                is_symlink = False
            case RarInfo():
                filename = self.info.filename
                is_dir = self.info.is_dir()
                is_file = self.info.is_file()
                is_symlink = self.info.is_symlink()
            case _:  # TarInfo
                filename = self.info.name
                is_dir = self.info.type == DIRTYPE
                is_file = self.info.type == REGTYPE
                is_symlink = self.info.type == SYMTYPE
        if filename is None:
            msg = f"Cannot create 7zr file, filename is None in source: {self.info}"
            raise ValueError(msg)
        return SevenZipInfo(
            filename,
            SevenZipInfoDefaults.compressed,
            SevenZipInfoDefaults.uncompressed,
            SevenZipInfoDefaults.archivable,
            is_dir,
            is_file,
            is_symlink,
            self.datetime(),
            SevenZipInfoDefaults.crc32,
        )
