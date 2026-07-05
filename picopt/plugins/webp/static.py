"""Still (non-animated) WebP handler."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from picopt.plugins.base import ImageHandler, PILSaveTool, Tool
from picopt.plugins.base.format import FileFormat
from picopt.plugins.png import Png
from picopt.plugins.webp.const import MODERN_CWEBP_FORMATS, WEBP_FORMAT_STR
from picopt.plugins.webp.tools import CWEBP_TOOL


class WebPLossless(ImageHandler):
    """Lossless still WebP handler."""

    OUTPUT_FORMAT_STR = WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WEBP_FORMAT_STR, lossless=True, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".webp",)

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"quality": 100, "method": 6, "lossless": True}
    )

    # Tier 1: convert non-acceptable inputs to PNG via Pillow. If the input
    #         is already in INPUT_FILE_FORMATS this is a no-op (pil_save
    #         short-circuits when self.input_file_format is acceptable).
    # Tier 2: encode to WebP. cwebp wins when available; otherwise Pillow
    #         saves directly to WebP.
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (
            PILSaveTool(
                target_format_str="PNG",
                save_kwargs={"compress_level": 0},
                name="pil2png",
            ),
        ),
        (
            CWEBP_TOOL,
            PILSaveTool(target_format_str=WEBP_FORMAT_STR, name="pil2webp"),
        ),
    )

    # https://developers.google.com/speed/webp/docs/cwebp
    _CWEBP_BASE_ARGS: tuple[str, ...] = (
        "-mt",
        "-q",
        "100",
        "-m",
        "6",
        "-o",
        "-",
        "-quiet",
        # https://groups.google.com/a/webmproject.org/g/webp-discuss/c/0GmxDmlexek
        "-lossless",
        "-sharp_yuv",
        "-alpha_filter",
        "best",
    )
    _NEAR_LOSSLESS_ARGS: tuple[str, ...] = ("-near_lossless", "0")

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Widen acceptable inputs if cwebp is modern enough for PPM/TIFF."""
        super().__init__(*args, **kwargs)
        if CWEBP_TOOL.is_modern:
            self._input_file_formats = self._input_file_formats | MODERN_CWEBP_FORMATS

    def cwebp_args(self) -> tuple[str, ...]:
        """Build the runtime cwebp argument tuple (no exec / input path)."""
        meta = ("all",) if self.config.keep_metadata else ("none",)
        args: tuple[str, ...] = (*self._CWEBP_BASE_ARGS, "-metadata", *meta)
        if self.config.near_lossless:
            args = (*args, *self._NEAR_LOSSLESS_ARGS)
        return args
