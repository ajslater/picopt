"""Optimize comic archives."""
import shutil
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Optional, Union

from confuse.templates import AttrDict
from termcolor import cprint

from picopt.data import PathInfo, ReportInfo
from picopt.handlers.handler import FileFormat, Handler, Metadata
from picopt.stats import ReportStats


class ContainerHandler(Handler, metaclass=ABCMeta):
    """Comic format class."""

    CONTAINER_DIR_SUFFIX: str = ".dir"
    CONVERT: bool = True

    @classmethod
    @abstractmethod
    def identify_format(cls, path: Path) -> Optional[FileFormat]:
        """Return the format if this handler can handle this path."""

    @abstractmethod
    def unpack_into(self) -> None:
        """Unpack a container into a tmp dir to work on it's contents."""

    @abstractmethod
    def pack_into(self, working_path: Path) -> None:
        """Create a container from a tmp dir's contents."""

    def __init__(
        self,
        config: AttrDict,
        path_info: PathInfo,
        file_format: FileFormat,
        metadata: Metadata,
    ):
        """Unpack a container with a subclass's unpacker."""
        super().__init__(
            config,
            path_info,
            file_format,
            metadata,
        )
        self.comment: Optional[bytes] = None
        self.tmp_container_dir: Path = Path(
            str(self.get_working_path()) + self.CONTAINER_DIR_SUFFIX
        )

    def unpack(self) -> Union[Handler, ReportStats]:
        """Create directory and unpack container."""
        try:
            if self.config.verbose:
                cprint(f"Unpacking {self.original_path}...", end="")

            # create a clean tmpdir
            if self.tmp_container_dir.exists():
                shutil.rmtree(self.tmp_container_dir)
            self.tmp_container_dir.mkdir(parents=True)

            # extract archive into the tmpdir
            self.unpack_into()

            if self.config.verbose:
                cprint("done")
        except Exception as exc:
            return self.error(exc)
        return self

    def cleanup_after_optimize(self, last_working_path: Path) -> tuple[int, int]:
        """Clean up the temp dir as well as the old container."""
        if self.config.verbose:
            cprint(".", end="")
        shutil.rmtree(self.tmp_container_dir)

        if self.config.verbose:
            cprint(".", end="")
        bytes_count = super().cleanup_after_optimize(last_working_path)

        if self.config.verbose:
            cprint("done.")
        return bytes_count

    def repack(self) -> ReportStats:
        """Create a new container and clean up the tmp dir."""
        new_path = self.get_working_path()
        try:
            # archive into new filename
            if self.config.verbose:
                cprint(f"Repacking {self.final_path}", end="")
            self.pack_into(new_path)

            bytes_count = self.cleanup_after_optimize(new_path)
            info = ReportInfo(
                self.final_path,
                self.convert,
                self.config.test,
                bytes_count[0],
                bytes_count[1],
            )
            report_stats = ReportStats(info)
            if self.config.verbose:
                report_stats.report()
        except Exception as exc:
            shutil.rmtree(self.tmp_container_dir, ignore_errors=True)
            return self.error(exc)
        return report_stats
