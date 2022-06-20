"""Format Superclass."""
from abc import ABCMeta
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.BmpImagePlugin import BmpImageFile
from PIL.PngImagePlugin import PngImageFile
from PIL.PpmImagePlugin import PpmImageFile
from PIL.TiffImagePlugin import TiffImageFile

from picopt.handlers.handler import Format, Handler
from picopt.stats import ReportStats


PPM_FORMAT_OBJ = Format(PpmImageFile.format, True, False)
BPM_FORMAT_OBJ = Format(BmpImageFile.format, True, False)
CONVERTABLE_FORMAT_OBJS = set((BPM_FORMAT_OBJ, PPM_FORMAT_OBJ))
CONVERTABLE_FORMATS = set([format.format for format in CONVERTABLE_FORMAT_OBJS])
PNG_ANIMATED_FORMAT_OBJ = Format(PngImageFile.format, True, True)
TIFF_FORMAT = TiffImageFile.format
TIFF_FORMAT_OBJ = Format(TIFF_FORMAT, True, False)
TIFF_ANIMATED_FORMAT_OBJ = Format(TIFF_FORMAT, True, True)
_NATIVE_ONLY_FORMATS = set(
    (PNG_ANIMATED_FORMAT_OBJ, TIFF_ANIMATED_FORMAT_OBJ, TIFF_FORMAT_OBJ)
)


class ImageHandler(Handler, metaclass=ABCMeta):
    """Format superclass."""

    PIL2_ARGS: dict[str, Any] = {}
    PREFERRED_PROGRAM: str = "unimplemented"

    def _optimize_with_progs(self) -> ReportStats:
        """
        Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        path = self.original_path
        for func in self.PROGRAMS.keys():
            if path != self.original_path:
                self.working_paths.add(path)
            new_path = self.get_working_path(func)
            path = getattr(self, func)(path, new_path)
            if self.BEST_ONLY:
                break

        bytes_count = self.cleanup_after_optimize(path)
        report_stats = ReportStats(
            self.final_path, bytes_count, self.config.test, self.convert
        )

        return report_stats

    def optimize_image(self) -> ReportStats:
        """Optimize a given image from a filename."""
        try:
            report_stats = self._optimize_with_progs()
            if self.config.verbose:
                report_stats.report()
        except Exception as exc:
            report_stats = self.error(exc)
        return report_stats

    def pil2native(self, old_path: Path, new_path: Path) -> Path:
        """Use PIL to save the image."""
        if (
            self.input_format_obj in _NATIVE_ONLY_FORMATS
            or self.PREFERRED_PROGRAM not in self.config._available_programs
        ):
            with Image.open(old_path) as image:
                image.save(
                    new_path,
                    self.OUTPUT_FORMAT,
                    exif=self.metadata.exif,
                    icc_profile=self.metadata.icc_profile,
                    **self.PIL2_ARGS,
                )
            image.close()  # for animated images
        else:
            new_path = old_path
        return new_path
