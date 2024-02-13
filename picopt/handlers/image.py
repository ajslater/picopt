"""FileFormat Superclass."""
from abc import ABCMeta
from collections.abc import Mapping
from io import BufferedReader, BytesIO
from types import MappingProxyType
from typing import Any, BinaryIO

from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.handlers.handler import Handler
from picopt.stats import ReportStats


class ImageHandler(Handler, metaclass=ABCMeta):
    """Image Handler superclass."""

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})
    PIL2PNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType({"compress_level": 0})
    CONVERGEABLE = frozenset()
    EMPTY_EXEC_ARGS: tuple[str, tuple[str, ...]] = ("", ())

    def _optimize_with_progs(self) -> ReportStats:
        """Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        max_iterations = 0
        stages = self.config.computed.handler_stages.get(self.__class__, {})
        if not stages:
            cprint(
                f"Tried to execute handler {self.__class__.__name__} with no available stages.",
                "yellow",
            )
            raise ValueError

        image_buffer: BinaryIO = self.path_info.fp_or_buffer()

        for func, exec_args in stages.items():
            loop = True
            converge = self.config.near_lossless and func in self.CONVERGEABLE
            iterations = 0
            while loop:
                if converge:
                    bytes_in = self.get_buffer_len(image_buffer)
                new_image_buffer: BinaryIO = getattr(self, func)(
                    exec_args, image_buffer
                )
                if image_buffer != new_image_buffer:
                    image_buffer.close()
                image_buffer = new_image_buffer
                if converge:
                    bytes_out = self.get_buffer_len(image_buffer)
                loop = converge and bytes_in > bytes_out  # type: ignore
                iterations += 1
            max_iterations = max(max_iterations, iterations)

        report_stats = self.cleanup_after_optimize(image_buffer)
        report_stats.iterations = max_iterations - 1
        return report_stats

    def optimize_image(self) -> ReportStats:
        """Optimize a given image from a filename."""
        try:
            report_stats = self._optimize_with_progs()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            report_stats = self.error(exc)
        if self.config.verbose:
            report_stats.report()

        return report_stats

    def pil2native(
        self,
        _exec_args: tuple[str, tuple[str, ...]],
        input_buffer: BytesIO | BufferedReader,
        format_str: None | str = None,
        opts: None | Mapping[str, Any] = None,
    ) -> BytesIO | BufferedReader:
        """Use PIL to save the image."""
        if self.input_file_format in self.INPUT_FILE_FORMATS:
            return input_buffer
        if format_str is None:
            format_str = self.OUTPUT_FORMAT_STR
        if opts is None:
            opts = self.PIL2_KWARGS

        info = self.prepare_info(format_str)

        output_buffer = BytesIO()
        with Image.open(input_buffer) as image:
            image.save(
                output_buffer,
                format_str,
                save_all=True,
                **opts,
                **info,
            )
        image.close()  # for animated images
        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return output_buffer

    def pil2png(
        self, _exec_args: tuple[str, ...], input_buffer: BytesIO | BufferedReader
    ) -> BytesIO | BufferedReader:
        """Internally convert unhandled formats to uncompressed png for cwebp."""
        return self.pil2native(
            self.EMPTY_EXEC_ARGS,
            input_buffer,
            format_str=PngImageFile.format,
            opts=self.PIL2PNG_KWARGS,
        )
