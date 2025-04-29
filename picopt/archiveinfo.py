"""Archive Info Converter."""

from datetime import datetime, timezone
from operator import attrgetter
from pathlib import Path
from tarfile import DIRTYPE, TarInfo
from zipfile import ZipInfo

from py7zr import FileInfo as SevenZipInfo
from rarfile import RarInfo

_DATETIME_ATTRGETTER = attrgetter(
    "year", "month", "day", "hour", "minute", "second", "microsecond"
)


class SevenZipInfoDefaults:
    """Defaults for SevenZip FileInfo."""

    compressed = True
    uncompressed = False
    archivable = True
    crc32 = None


class ArchiveInfo:
    """Archive Info Converter."""

    def __init__(self, info: TarInfo | RarInfo | ZipInfo | SevenZipInfo):
        """Store the source info."""
        self.info = info
        self._filename = None
        self._is_dir = None
        self._mtime = None
        self._dttm = None
        if isinstance(self.info, RarInfo):
            # This weird hack because
            # Some instances of RarInfo don't serialize properly for multiprocessing
            self.info = self.to_zipinfo()

    def filename(self):
        """Return archive filename."""
        if self._filename is None:
            if isinstance(self.info, ZipInfo | SevenZipInfo | RarInfo):
                self._filename = self.info.filename or ""
            elif isinstance(self.info, TarInfo):
                self._filename = self.info.name or ""
            else:
                reason = f"{self.info} is not a type with a known filename."
                raise TypeError(reason)
        return self._filename

    def rename(self, filename: str | Path):
        """Rename archiveinfo."""
        filename = str(filename)
        if isinstance(self.info, ZipInfo | SevenZipInfo):
            self.info.filename = filename
        elif isinstance(self.info, TarInfo):
            self.info.name = filename
        else:
            reason = f"{self.info} cannot be renamed."
            raise TypeError(reason)

        # clear filename cache
        self._filename = None

    def is_dir(self):
        """Is a directory."""
        if self._is_dir is None:
            if isinstance(self.info, ZipInfo | RarInfo):
                self._is_dir = self.info.is_dir()
            elif isinstance(self.info, TarInfo):
                self._is_dir = self.info.type == DIRTYPE
            elif isinstance(self.info, SevenZipInfo):
                self._is_dir = bool(self.info.is_directory)
            else:
                reason = f"{self.info} is not a type with a known filetype."
                raise TypeError(reason)
        return self._is_dir

    def datetime(self):
        """Return mtime as a datetime."""
        if self._dttm is None:
            if isinstance(self.info, ZipInfo):
                if date_time := self.info.date_time:
                    self._dttm = datetime(*date_time, tzinfo=timezone.utc)
            elif isinstance(self.info, TarInfo):
                self._dttm = datetime.fromtimestamp(self.info.mtime, tz=timezone.utc)
            elif isinstance(self.info, SevenZipInfo):
                self._dttm = self.info.creationtime
            elif isinstance(self.info, RarInfo):
                if dttm := self.info.mtime:
                    self._dttm = dttm
            else:
                reason = f"{self.info} is not a type with timestamp."
                raise TypeError(reason)
        return self._dttm

    def mtime(self):
        """Return Modified Timestamp."""
        if self._mtime is None:
            if isinstance(self.info, SevenZipInfo | ZipInfo | RarInfo):
                dttm = self.datetime()
                if dttm is not None:
                    self._mtime = dttm.timestamp()
            elif isinstance(self.info, TarInfo):
                self._mtime = self.info.mtime
            else:
                reason = f"{self.info} is not a type with timestamp."
                raise TypeError(reason)
        return self._mtime

    def to_zipinfo(self):
        """Convert to ZipInfo."""
        if isinstance(self.info, ZipInfo):
            info = self.info
        elif isinstance(self.info, RarInfo):
            kwargs = {}
            if filename := self.filename():
                kwargs["filename"] = filename
            if self.info.date_time:
                kwargs["date_time"] = self.info.date_time
            info = ZipInfo(**kwargs)
        elif isinstance(self.info, TarInfo | SevenZipInfo):
            date_time = _DATETIME_ATTRGETTER(self.datetime())
            info = ZipInfo(filename=self.filename(), date_time=date_time)
        else:
            reason = f"{self.info} cannot be converted to ZipInfo"
            raise TypeError(reason)
        return info

    def to_tarinfo(self):
        """Convert to TarInfo."""
        if isinstance(self.info, TarInfo):
            info = self.info
        elif isinstance(self.info, RarInfo | SevenZipInfo | ZipInfo):
            kwargs = {}
            if isinstance(self.info, ZipInfo | RarInfo):
                if name := self.filename():
                    kwargs["name"] = name
            elif isinstance(self.info, SevenZipInfo):
                kwargs["name"] = self.info.filename
            info = TarInfo(**kwargs)
            mtime = self.mtime()
            if mtime is not None:
                info.mtime = mtime
        else:
            reason = f"{self.info} cannot be converted to TarInfo"
            raise TypeError(reason)
        return info

    def to_sevenzipinfo(self):
        """Convert to SevenZip FileInfo."""
        if isinstance(self.info, SevenZipInfo):
            info = self.info
        elif isinstance(self.info, ZipInfo | RarInfo):
            info = SevenZipInfo(
                self.info.filename,
                SevenZipInfoDefaults.compressed,
                SevenZipInfoDefaults.uncompressed,
                SevenZipInfoDefaults.archivable,
                self.info.is_dir(),
                self.datetime(),
                SevenZipInfoDefaults.crc32,
            )
        elif isinstance(self.info, TarInfo):
            is_dir = self.info.type == DIRTYPE
            info = SevenZipInfo(
                self.info.name,
                SevenZipInfoDefaults.compressed,
                SevenZipInfoDefaults.uncompressed,
                SevenZipInfoDefaults.archivable,
                is_dir,
                self.datetime(),
                SevenZipInfoDefaults.crc32,
            )
        else:
            reason = f"{self.info} cannot be converted to SevenZip FileInfo"
            raise TypeError(reason)

        return info
