"""Archive Info Converter."""

from dataclasses import dataclass
from datetime import UTC, datetime
from operator import attrgetter
from pathlib import Path
from stat import S_IFDIR, S_IFREG, S_IMODE
from tarfile import DIRTYPE, REGTYPE, SYMTYPE, TarInfo
from typing import Final, TypeAlias, assert_never
from zipfile import ZipInfo

from py7zr import FileInfo as SevenZipInfo
from py7zr.py7zr import FileInfo
from rarfile import RarInfo

_DATETIME_ATTRGETTER = attrgetter(
    "year", "month", "day", "hour", "minute", "second", "microsecond"
)
# The zip format cannot represent timestamps before 1980; zipfile raises on
# them. Clamp older (or missing) member times to the epoch zipfile accepts.
_ZIP_EPOCH: Final = (1980, 1, 1, 0, 0, 0)
# drwxr-xr-x in the unix high word, plus the MS-DOS directory flag.
_ZIP_DIR_ATTR: Final = ((S_IFDIR | 0o755) << 16) | 0x10
# rw-r--r-- for converted files that bring no usable unix mode: rar members,
# 7z members without one, and links.
_DEFAULT_FILE_MODE: Final = 0o644
ArchiveInfoType: TypeAlias = TarInfo | RarInfo | ZipInfo | SevenZipInfo


@dataclass
class SevenZipMemberInfo(SevenZipInfo):
    """py7zr's FileInfo plus the member attributes its list() drops."""

    # Raw 7z attributes: Windows flags, and a unix type and mode when present.
    attributes: int | None = None
    posix_mode: int | None = None


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
        # True when the member came from a real zip; repack then preserves
        # its compression method instead of choosing one by content.
        self.is_native_zipinfo: bool = isinstance(info, ZipInfo)
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
            match info := self.info:
                case TarInfo():
                    self._filename = info.name or ""
                case ZipInfo() | SevenZipInfo() | RarInfo():
                    self._filename = info.filename or ""
                case _:
                    assert_never(info)
        return self._filename

    def rename(self, filename: str | Path) -> None:
        """Rename archiveinfo."""
        filename = str(filename)
        match info := self.info:
            case ZipInfo() | SevenZipInfo():
                info.filename = filename
            case TarInfo():
                info.name = filename
            case RarInfo():
                msg = f"{info} cannot be renamed."
                raise TypeError(msg)
            case _:
                assert_never(info)

        # clear filename cache
        self._filename = None

    def is_dir(self) -> bool:
        """Is a directory."""
        if self._is_dir is None:
            match info := self.info:
                case ZipInfo() | RarInfo():
                    self._is_dir = info.is_dir()
                case TarInfo():
                    self._is_dir = info.isdir()
                case SevenZipInfo():
                    self._is_dir = bool(info.is_directory)
                case _:
                    assert_never(info)
        return self._is_dir

    def datetime(self) -> datetime | None:
        """Return mtime as a datetime."""
        if self._dttm is None:
            dttm: datetime | None = None
            match info := self.info:
                case ZipInfo():
                    if date_time := info.date_time:
                        dttm = datetime(*date_time)  # noqa: DTZ001
                case TarInfo():
                    dttm = datetime.fromtimestamp(info.mtime, tz=UTC)
                case SevenZipInfo():
                    dttm = info.creationtime
                case RarInfo():
                    dttm = info.mtime or None
                case _:
                    assert_never(info)

            if dttm:
                if not dttm.tzinfo:
                    dttm = dttm.replace(tzinfo=UTC)
                self._dttm = dttm
        return self._dttm

    def mtime(self) -> float | None:
        """Return Modified Timestamp."""
        if self._mtime is None:
            match info := self.info:
                case TarInfo():
                    self._mtime = info.mtime
                case SevenZipInfo() | ZipInfo() | RarInfo():
                    dttm = self.datetime()
                    if dttm is not None:
                        self._mtime = dttm.timestamp()
                case _:
                    assert_never(info)
        return self._mtime

    def _file_mode(self) -> int:
        """Return a regular member's own permission bits, else rw-r--r--."""
        match src := self.info:
            case TarInfo() if src.isreg():
                return S_IMODE(src.mode)
            case SevenZipMemberInfo(is_file=True, posix_mode=int() as mode):
                return mode
            case _:
                return _DEFAULT_FILE_MODE

    def to_zipinfo(self) -> ZipInfo:
        """Convert to ZipInfo."""
        match src := self.info:
            case ZipInfo():
                return src
            case RarInfo():
                filename = self.filename() or "NoName"
                date_time = tuple(src.date_time) if src.date_time else _ZIP_EPOCH
            case TarInfo() | SevenZipInfo():
                filename = self.filename()
                dttm = self.datetime()
                date_time = _DATETIME_ATTRGETTER(dttm)[:6] if dttm else _ZIP_EPOCH
            case _:
                assert_never(src)
        date_time = max(date_time, _ZIP_EPOCH)
        if not self.is_dir():
            # Without a mode ZipFile writes ?rw------- (0o600, no file type).
            info = ZipInfo(filename=filename, date_time=date_time)
            info.external_attr = (S_IFREG | self._file_mode()) << 16
            return info
        # Tar and 7z directory names lack the trailing slash that marks a
        # zip directory; without it the entry extracts as an empty file.
        info = ZipInfo(filename=filename.rstrip("/") + "/", date_time=date_time)
        info.external_attr = _ZIP_DIR_ATTR
        return info

    def to_tarinfo(self) -> TarInfo:
        """Convert to TarInfo."""
        match src := self.info:
            case TarInfo():
                return src
            case ZipInfo() | RarInfo():
                kwargs = {}
                if name := self.filename():
                    kwargs["name"] = name
            case SevenZipInfo():
                kwargs = {"name": src.filename}
            case _:
                assert_never(src)
        info = TarInfo(**kwargs)
        mtime = self.mtime()
        if mtime is not None:
            info.mtime = mtime
        return info

    def to_sevenzipinfo(self) -> FileInfo:
        """Convert to SevenZip FileInfo."""
        match src := self.info:
            case SevenZipInfo():
                return src
            case ZipInfo():
                filename = src.filename
                is_dir = src.is_dir()
                # ZipInfo has no is_file() or is_symlink().
                is_file = not is_dir
                is_symlink = False
            case RarInfo():
                filename = src.filename
                is_dir = src.is_dir()
                is_file = src.is_file()
                is_symlink = src.is_symlink()
            case TarInfo():
                filename = src.name
                is_dir = src.type == DIRTYPE
                is_file = src.type == REGTYPE
                is_symlink = src.type == SYMTYPE
            case _:
                assert_never(src)
        if filename is None:
            msg = f"Cannot create 7zr file, filename is None in source: {src}"
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
