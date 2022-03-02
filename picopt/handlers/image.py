"""Format Superclass."""
from abc import ABCMeta

from PIL.BmpImagePlugin import BmpImageFile
from PIL.PpmImagePlugin import PpmImageFile

from picopt.handlers.handler import Format, Handler
from picopt.stats import ReportStats


PPM_FORMAT = Format(PpmImageFile.format, True, False)
BPM_FORMAT = Format(BmpImageFile.format, True, False)
CONVERTABLE_FORMATS = set((BPM_FORMAT, PPM_FORMAT))
CONVERTABLE_FORMAT_STRS = set([format.format for format in CONVERTABLE_FORMATS])


class ImageHandler(Handler, metaclass=ABCMeta):
    """Format superclass."""

    def _optimize_with_progs(self) -> ReportStats:
        """
        Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        path = self.original_path
        for func in self.PROGRAMS:
            print(f"{func} {path}")
            if path != self.original_path:
                self.working_paths.add(path)
            new_path = self.get_working_path(func)
            path = getattr(self, func)(path, new_path)
            if self.BEST_ONLY:
                break

        bytes_count = self.cleanup_after_optimize(path)
        report_stats = ReportStats(
            self.config, self.final_path, bytes_count=bytes_count
        )

        return report_stats

    def optimize_image(self) -> ReportStats:
        """Optimize a given image from a filename."""
        try:
            report_stats = self._optimize_with_progs()
            report_stats.report_saved()
        except Exception as exc:
            report_stats = self.error(exc)
        return report_stats
