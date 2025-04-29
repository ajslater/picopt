"""Handler Cleanup."""

import os
from io import BufferedReader, BytesIO
from typing import BinaryIO

from picopt.handlers.handler.init import HandlerInit
from picopt.report import ReportStats


class HandlerCleanup(HandlerInit):
    """Handler cleanup methods."""

    def _get_buffer_len(self, buffer: BinaryIO) -> int:
        """Return buffer size."""
        if isinstance(buffer, BufferedReader):
            size = self.working_path.stat().st_size
        elif isinstance(buffer, BytesIO):
            size = buffer.getbuffer().nbytes
        else:
            reason = f"Unknown type for input_buffer: {type(buffer)}"
            raise TypeError(reason)
        return size

    def _cleanup_after_optimize_calculate_bytes(
        self, final_data_buffer: BinaryIO
    ) -> tuple[int, int]:
        bytes_in = self.path_info.bytes_in()
        bytes_out = self._get_buffer_len(final_data_buffer)
        return bytes_in, bytes_out

    def _cleanup_after_optimize_save_new(
        self, final_data_buffer: BinaryIO | None
    ) -> bytes:
        """Save new data."""
        return_data = b""
        if final_data_buffer is None:
            return return_data
        if isinstance(final_data_buffer, BytesIO) or bool(self.path_info.archiveinfo):
            # only return the data in the report for containers.
            final_data_buffer.seek(0)
            return_data = final_data_buffer.read()
        return return_data

    def _cleanup_filesystem_write_final_path(self, final_data_buffer: BinaryIO) -> None:
        if isinstance(final_data_buffer, BytesIO):
            with self.final_path.open("wb") as final_file:
                final_data_buffer.seek(0)
                final_file.write(final_data_buffer.read())
        else:
            self.working_path.replace(self.final_path)

    def _cleanup_filesystem_cleanup_original_path(self):
        """Remove original path if the file has a new name."""
        compare_final_str = str(self.final_path)
        compare_original_str = str(self.original_path)
        if not self.path_info.is_case_sensitive:
            # Be careful of case sensitive fs.
            compare_final_str = compare_final_str.lower()
            compare_original_str = compare_original_str.lower()
        if compare_final_str != compare_original_str:
            self.original_path.unlink(missing_ok=True)

    def _cleanup_filesystem_preserve_stats(self):
        if not self.config.preserve:
            return
        stat = self.path_info.stat()
        if not stat or stat is True:
            return

        os.chown(self.final_path, stat.st_uid, stat.st_gid)
        self.final_path.chmod(stat.st_mode)
        os.utime(
            self.final_path,
            ns=(stat.st_atime_ns, stat.st_mtime_ns),
        )

    def _cleanup_filesystem(self, final_data_buffer: BinaryIO) -> None:
        """Write file to filesystem and clean up."""
        if not self.final_path:
            reason = "This should not happen. no buffer and no final path."
            raise ValueError(reason)
        self._cleanup_filesystem_write_final_path(final_data_buffer)
        # Can early close here
        final_data_buffer.close()
        self._cleanup_filesystem_cleanup_original_path()
        self._cleanup_filesystem_preserve_stats()

    def _cleanup_after_optimize(self, final_data_buffer: BinaryIO) -> ReportStats:
        """Replace old file with better one or discard new wasteful file."""
        bytes_in, bytes_out = self._cleanup_after_optimize_calculate_bytes(
            final_data_buffer
        )
        if not self.config.dry_run and (
            (bytes_out > 0) and ((bytes_out < bytes_in) or self.config.bigger)
        ):
            return_data = self._cleanup_after_optimize_save_new(final_data_buffer)
            if self.path_info.path:
                self._cleanup_filesystem(final_data_buffer)
        else:
            return_data = b""
        final_data_buffer.close()
        if (
            self.working_path
            and self.working_path != self.final_path
            and isinstance(final_data_buffer, BufferedReader)
        ):
            self.working_path.unlink(missing_ok=True)
        if self.original_path != self.final_path:
            self.path_info.rename(self.final_path)
        return ReportStats(
            self.final_path,
            path_info=self.path_info,
            config=self.config,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            data=return_data,
        )
