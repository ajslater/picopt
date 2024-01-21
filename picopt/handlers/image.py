"""FileFormat Superclass."""
from abc import ABCMeta
from pathlib import Path
from types import MappingProxyType
from typing import Any

from PIL import Image

from picopt.data import ReportInfo
from picopt.handlers.handler import Handler
from picopt.stats import ReportStats


class ImageHandler(Handler, metaclass=ABCMeta):
    """Image Handler superclass."""

    PIL2_ARGS: MappingProxyType[str, Any] = MappingProxyType({})
    PREFERRED_PROGRAM: str = "unimplemented"
    CONVERGEABLE = False

    def _optimize_with_progs(self) -> ReportStats:
        """Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        path = self.original_path
        max_iterations = 0
        for func in self.PROGRAMS:
            if path != self.original_path:
                self.working_paths.add(path)

            converge = self.CONVERGEABLE and self.config.exhaustive
            loop = True
            bytes_in = 0
            bytes_out = 0
            iterations = 0
            while loop:
                if converge:
                    bytes_in = path.stat().st_size
                new_path = self.get_working_path(func)
                path = getattr(self, func)(path, new_path)
                if converge:
                    bytes_out = path.stat().st_size
                loop = (
                    converge and path.suffix == new_path.suffix and bytes_in > bytes_out
                )
                iterations += 1
            max_iterations = max(max_iterations, iterations)

            if self.BEST_ONLY:
                break

        bytes_count = self.cleanup_after_optimize(path)
        info = ReportInfo(
            self.final_path,
            self.convert,
            self.config.test,
            bytes_count[0],
            bytes_count[1],
            iterations=max_iterations,
        )
        return ReportStats(info)

    def optimize_image(self) -> ReportStats:
        """Optimize a given image from a filename."""
        try:
            report_stats = self._optimize_with_progs()
            if self.config.verbose:
                report_stats.report()
        except Exception as exc:
            report_stats = self.error(exc)
        return report_stats

    def pil2native(
        self, old_path: Path, new_path: Path, format_str: None | str = None
    ) -> Path:
        """Use PIL to save the image."""
        if (
            self.input_file_format in self.INPUT_FILE_FORMATS
            and self.PREFERRED_PROGRAM in self.config.computed.available_programs
        ):
            return old_path
        if format_str is None:
            format_str = self.OUTPUT_FORMAT_STR
        with Image.open(old_path) as image:
            image.save(
                new_path,
                format_str,
                exif=self.metadata.exif,
                icc_profile=self.metadata.icc_profile,
                **self.PIL2_ARGS,
            )
        image.close()  # for animated images
        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return new_path
