"""Optimize comic archives."""
import shutil

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from confuse.templates import AttrDict

from picopt.handlers.handler import Format, Handler
from picopt.stats import ReportStats


class ContainerHandler(Handler, metaclass=ABCMeta):
    """Comic format class."""

    CONTAINER_DIR_SUFFIX = "dir"

    @classmethod
    @abstractmethod
    def can_handle(cls, path: Path) -> Optional[Format]:
        """Can this handler handle this file type."""
        pass

    @abstractmethod
    def unpack_into(self) -> None:
        """Unpack a container into a tmp dir to work on it's contents."""
        pass

    @abstractmethod
    def create_container(self, working_path: Path) -> None:
        """Create a container from a tmp dir's contents."""
        pass

    def __init__(self, config: AttrDict, original_path: Path, format: Format):
        """Unpack a container with a subclass's unpacker."""
        super().__init__(config, original_path, format)
        self.comment: Optional[bytes] = None
        self.tmp_container_dir: Path = Path(
            str(self.get_working_path()) + self.CONTAINER_DIR_SUFFIX
        )

    def unpack(self):
        """Create directory and unpack container."""
        try:
            if self.config.verbose:
                print(f"Extracting {self.original_path}...", end="")

            # create a clean tmpdir
            if self.tmp_container_dir.exists():
                shutil.rmtree(self.tmp_container_dir)
            self.tmp_container_dir.mkdir(parents=True)

            # extract archive into the tmpdir
            self.unpack_into()

            if self.config.verbose:
                print("done")
        except Exception as exc:
            print(exc)
            raise exc

    def cleanup_after_optimize(self, working_path: Path) -> Tuple[int, int]:
        """Clean up the temp dir as well as thte old container."""
        if self.config.verbose:
            print(".", end="")
        shutil.rmtree(self.tmp_container_dir)

        if self.config.verbose:
            print(".", end="")
        bytes_count = super().cleanup_after_optimize(working_path)

        if self.config.verbose:
            print("done.")
        return bytes_count

    def repack(self) -> ReportStats:
        """Create a new container and clean up the tmp dir."""
        try:
            # archive into new filename
            # XXX should create_container specify the path?
            new_path = self.get_working_path()
            self.create_container(new_path)

            bytes_count = self.cleanup_after_optimize(new_path)
            report_stats = ReportStats(self.final_path, bytes_count=bytes_count)
            if self.config.verbose:
                report_stats.report(self.config.test)
            return report_stats
        except Exception as exc:
            print(exc)
            raise exc
