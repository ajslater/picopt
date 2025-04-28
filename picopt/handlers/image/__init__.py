"""FileFormat Superclass."""

from abc import ABC
from collections.abc import Mapping
from io import BufferedReader, BytesIO
from types import MappingProxyType
from typing import Any, BinaryIO

from PIL import Image
from PIL.PngImagePlugin import PngImageFile

from picopt.handlers.handler import Handler
from picopt.handlers.metadata import PrepareInfoMixin


class ImageHandler(PrepareInfoMixin, Handler, ABC):
    """Image Handler superclass."""

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})
    _PIL2PNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"compress_level": 0}
    )
    _EMPTY_EXEC_ARGS: tuple[str, tuple[str, ...]] = ("", ())

    def __init__(self, *args, info: Mapping[str, Any], **kwargs):
        """Save image info metadata."""
        super().__init__(*args, **kwargs)
        # For image metadata preservation
        self.set_info(info)

    def optimize(self) -> BinaryIO:
        """
        Use the correct optimizing functions in sequence.

        And report back statistics.
        """
        stages = self.config.computed.handler_stages.get(self.__class__, {})
        if not stages:
            self._printer.warn(
                f"Tried to execute handler {self.__class__.__name__} with no available stages.",
            )
            raise ValueError

        image_buffer: BinaryIO = self.path_info.fp_or_buffer()

        for func_name, exec_args in stages.items():
            func = getattr(self, func_name)
            new_image_buffer: BinaryIO = func(exec_args, image_buffer)
            if image_buffer != new_image_buffer:
                image_buffer.close()
            image_buffer = new_image_buffer

        return image_buffer

    def pil2native(
        self,
        _exec_args: tuple[str, tuple[str, ...]],
        input_buffer: BytesIO | BufferedReader,
        format_str: None | str = None,
        opts: None | Mapping[str, Any] = None,
    ) -> BytesIO | BufferedReader:
        """Use PIL to save the image."""
        if self.input_file_format in self._input_file_formats:
            # if we're already in an acceptable format we don't need to use PIL to
            # convert
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
            self._EMPTY_EXEC_ARGS,
            input_buffer,
            format_str=PngImageFile.format,
            opts=self._PIL2PNG_KWARGS,
        )
