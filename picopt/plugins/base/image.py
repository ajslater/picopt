"""
Image handler base.

This is the merger of the old ``handlers/image/__init__.py`` with the
``PrepareInfoMixin`` from ``handlers/mixins.py``. PIL info preparation is
not a "mixin" in any meaningful sense — it's a hard part of being an image
handler. Folding it in removes the multiple-inheritance noise.
"""

from __future__ import annotations

from io import BufferedReader, BytesIO
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, BinaryIO

from loguru import logger
from PIL import Image
from PIL.PngImagePlugin import PngImageFile, PngInfo
from PIL.WebPImagePlugin import WebPImageFile
from typing_extensions import override

from picopt.plugins.base.format import PNGINFO_XMP_KEY, FileFormat
from picopt.plugins.base.handler import Handler

if TYPE_CHECKING:
    from collections.abc import Mapping


_SAVE_INFO_KEYS: frozenset[str] = frozenset(
    {"n_frames", "loop", "duration", "background"}
)


def _gif_palette_index_to_rgb(palette_index: int) -> tuple[int, int, int]:
    """Convert an 8-bit color palette index to an RGB tuple."""
    red = ((palette_index >> 5) & 0x7) * 36
    green = ((palette_index >> 2) & 0x7) * 36
    blue = (palette_index & 0x3) * 36
    return (red, green, blue)


class ImageHandler(Handler):
    """Base class for image handlers."""

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})

    def __init__(
        self,
        *args: Any,
        info: Mapping[str, Any],
        **kwargs: Any,
    ) -> None:
        """Save image info metadata."""
        super().__init__(*args, **kwargs)
        self.info: dict[str, Any] = dict(info)

    # --------------------------------------------------------- info munging

    def _prepare_info_webp(self) -> None:
        background = self.info.pop("background", None)
        if isinstance(background, int):
            rgb = _gif_palette_index_to_rgb(background)
            self.info["background"] = (*rgb, 0)

    def _prepare_info_png(self) -> None:
        transparency = self.info.get("transparency")
        if isinstance(transparency, int):
            self.info.pop("transparency", None)
        if xmp := self.info.get("xmp", None):
            pnginfo = self.info.get("pnginfo", PngInfo())
            pnginfo.add_text(PNGINFO_XMP_KEY, xmp, zip=True)
            self.info["pnginfo"] = pnginfo

    def prepare_info(self, format_str: str) -> MappingProxyType[str, Any]:
        """Prepare an info dict suitable for ``Image.save``."""
        if format_str == WebPImageFile.format:
            self._prepare_info_webp()
        elif format_str == PngImageFile.format:
            self._prepare_info_png()
        if self.config.keep_metadata:
            return MappingProxyType(self.info)
        info: dict[str, Any] = {
            key: val for key, val in self.info.items() if key in _SAVE_INFO_KEYS
        }
        return MappingProxyType(info)

    # ----------------------------------------------------------- pil_save

    def pil_save(
        self,
        input_buffer: BytesIO | BufferedReader | BinaryIO,
        format_str: str,
        opts: Mapping[str, Any],
    ) -> BytesIO | BufferedReader | BinaryIO:
        """
        Save the buffer through PIL into the requested format.

        If the input is already in an acceptable format for this handler,
        skip the round-trip and return the buffer untouched.
        """
        if self.input_file_format in self._input_file_formats:
            return input_buffer
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
        image.close()  # animated images need a double close
        self.input_file_format = FileFormat(
            format_str,
            lossless=self.OUTPUT_FILE_FORMAT.lossless,
            animated=self.OUTPUT_FILE_FORMAT.animated,
        )
        return output_buffer

    # ----------------------------------------------------------- pipeline

    @override
    def optimize(self) -> BinaryIO:
        """Run each pipeline stage in sequence."""
        stages = self.selected_stages()
        if not stages:
            logger.warning(
                f"Tried to execute handler {type(self).__name__} with no "
                "available pipeline stages."
            )
            msg = f"No pipeline stages available for {type(self).__name__}"
            raise ValueError(msg)
        buf: BinaryIO = self.path_info.fp_or_buffer()
        for tool in stages:
            new_buf = tool.run_stage(self, buf)
            if buf is not new_buf:
                buf.close()
            buf = new_buf
        return buf
