"""Optimize comic archives."""
import shutil

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Optional, Union

from confuse.templates import AttrDict

from picopt.handlers.handler import Format, Handler, Metadata
from picopt.stats import ReportStats


class ContainerHandler(Handler, metaclass=ABCMeta):
    """Comic format class."""

    CONTAINER_DIR_SUFFIX: str = ".dir"
    CONVERT: bool = True

    @classmethod
    @abstractmethod
    def identify_format(cls, path: Path) -> Optional[Format]:
        """Return the format if this handler can handle this path."""
        pass

    @abstractmethod
    def unpack_into(self) -> None:
        """Unpack a container into a tmp dir to work on it's contents."""
        pass

    @abstractmethod
    def pack_into(self, working_path: Path) -> None:
        """Create a container from a tmp dir's contents."""
        pass

    def __init__(
        self,
        config: AttrDict,
        original_path: Path,
        format: Format,
        metadata: Metadata,
        is_case_sensitive: bool,
    ):
        """Unpack a container with a subclass's unpacker."""
        super().__init__(config, original_path, format, metadata, is_case_sensitive)
        self.comment: Optional[bytes] = None
        self.tmp_container_dir: Path = Path(
            str(self.get_working_path()) + self.CONTAINER_DIR_SUFFIX
        )

    def unpack(self) -> Union[Handler, ReportStats]:
        """Create directory and unpack container."""
        try:
            if self.config.verbose:
                print(f"Unpacking {self.original_path}...", end="")

            # create a clean tmpdir
            if self.tmp_container_dir.exists():
                shutil.rmtree(self.tmp_container_dir)
            self.tmp_container_dir.mkdir(parents=True)

            # extract archive into the tmpdir
            self.unpack_into()

            if self.config.verbose:
                print("done")
            return self
        except Exception as exc:
            return self.error(exc)

    def cleanup_after_optimize(self, working_path: Path) -> tuple[int, int]:
        """Clean up the temp dir as well as the old container."""
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
            new_path = self.get_working_path()
            if self.config.verbose:
                print(f"Repacking {self.final_path}", end="")
            self.pack_into(new_path)

            bytes_count = self.cleanup_after_optimize(new_path)
            report_stats = ReportStats(
                self.final_path, bytes_count, self.config.test, self.convert
            )
            if self.config.verbose:
                report_stats.report()
            return report_stats
        except Exception as exc:
            return self.error(exc)
