"""FileFormat Superclass."""
from abc import ABCMeta
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from PIL import Image
from termcolor import cprint

from picopt.data import ReportInfo
from picopt.handlers.handler import Handler
from picopt.stats import ReportStats


class ImageHandler(Handler, metaclass=ABCMeta):
    """Image Handler superclass."""

    # TODO PIL2_KWARGS
    PIL2_ARGS: MappingProxyType[str, Any] = MappingProxyType({})
    CONVERGEABLE = frozenset()
    EMPTY_EXEC_ARGS: tuple[str, tuple[str, ...]] = ("", ())

    def _optimize_with_progs(self) -> ReportStats:
        """Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        path = self.original_path
        max_iterations = 0
        stages = self.config.computed.handler_stages.get(self.__class__, {})
        if not stages:
            cprint(
                f"Tried to execute handler {self.__class__.__name__} with no available stages.",
                "yellow",
            )
            raise ValueError

        for func, exec_args in stages.items():
            if path != self.original_path:
                self.working_paths.add(path)

            converge = self.config.exhaustive and func in self.CONVERGEABLE
            loop = True
            bytes_in = 0
            bytes_out = 0
            iterations = 0
            while loop:
                if converge:
                    bytes_in = path.stat().st_size
                new_path = self.get_working_path(func)
                path = getattr(self, func)(exec_args, path, new_path)
                if converge:
                    bytes_out = path.stat().st_size
                loop = (
                    converge and path.suffix == new_path.suffix and bytes_in > bytes_out
                )
                iterations += 1
            max_iterations = max(max_iterations, iterations)

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
            import traceback

            traceback.print_exc()
            report_stats = self.error(exc)
        return report_stats

    def pil2native(  # noqa: PLR0913
        self,
        exec_args: tuple[str, tuple[str, ...]],  # noqa: ARG002
        old_path: Path,
        new_path: Path,
        format_str: None | str = None,
        opts: None | Mapping[str, Any] = None,
    ) -> Path:
        """Use PIL to save the image."""
        if (
            # TODO this is only for the ones that come first, not for optimizing.
            self.input_file_format in self.INPUT_FILE_FORMATS
            # TODO REMOVE
            # and self.PREFERRED_PROGRAM in self.config.computed.available_programs
        ):
            return old_path
        if format_str is None:
            format_str = self.OUTPUT_FORMAT_STR
        if opts is None:
            opts = self.PIL2_ARGS
        info = self.prepare_info(format_str)

        with Image.open(old_path) as image:
            image.save(
                new_path,
                format_str,
                save_all=True,
                **opts,
                **info,  # TODO possibly filter only for valid keys firs)t
            )
        image.close()  # for animated images
        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return new_path
