"""Format Superclass."""
from abc import ABCMeta

from PIL.BmpImagePlugin import BmpImageFile
from PIL.PpmImagePlugin import PpmImageFile

from picopt.handlers.handler import Format, Handler
from picopt.stats import ReportStats


PPM_FORMAT_OBJ = Format(PpmImageFile.format, True, False)
BPM_FORMAT_OBJ = Format(BmpImageFile.format, True, False)
CONVERTABLE_FORMAT_OBJS = set((BPM_FORMAT_OBJ, PPM_FORMAT_OBJ))
CONVERTABLE_FORMATS = set([format.format for format in CONVERTABLE_FORMAT_OBJS])


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
        report_stats = ReportStats(self.final_path, bytes_count=bytes_count)

        return report_stats

    def optimize_image(self) -> ReportStats:
        """Optimize a given image from a filename."""
        try:
            report_stats = self._optimize_with_progs()
            if self.config.verbose:
                report_stats.report(self.config.test)
        except Exception as exc:
            report_stats = self.error(exc)
        return report_stats
