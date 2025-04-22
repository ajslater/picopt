"""Image metadata preservation."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from PIL.PngImagePlugin import PngImageFile, PngInfo
from PIL.WebPImagePlugin import WebPImageFile

from picopt.formats import PNGINFO_XMP_KEY
from picopt.handlers.handler import Handler

_SAVE_INFO_KEYS: frozenset[str] = frozenset(
    {"n_frames", "loop", "duration", "background"}
)


def _gif_palette_index_to_rgb(
    palette_index: int,
) -> tuple[int, int, int]:
    """Convert an 8-bit color palette index to an RGB tuple."""
    # Extract the individual color components from the palette index.
    red = (palette_index >> 5) & 0x7
    green = (palette_index >> 2) & 0x7
    blue = palette_index & 0x3

    # Scale the color components to the range 0-255.
    red = red * 36
    green = green * 36
    blue = blue * 36

    return (red, green, blue)


class PrepareInfoMixin(Handler):
    """Prepare to write stored metadata."""

    def set_info(self, info: Mapping[str, Any]):
        """Set metadata."""
        self.info: dict[str, Any] = dict(info)

    def _prepare_info_webp(self):
        """Transform info for webp."""
        background = self.info.pop("background", None)
        if isinstance(background, int):
            # GIF background is an int.
            rgb = _gif_palette_index_to_rgb(background)
            self.info["background"] = (*rgb, 0)

    def _prepare_info_png(self):
        """Transform info for png."""
        transparency = self.info.get("transparency")
        if isinstance(transparency, int):
            self.info.pop("transparency", None)
        if xmp := self.info.get("xmp", None):
            pnginfo = self.info.get("pnginfo", PngInfo())
            pnginfo.add_text(PNGINFO_XMP_KEY, xmp, zip=True)
            self.info["pnginfo"] = pnginfo

    def prepare_info(self, format_str) -> MappingProxyType[str, Any]:
        """Prepare an info dict for saving."""
        if format_str == WebPImageFile.format:
            self._prepare_info_webp()
        elif format_str == PngImageFile.format:
            self._prepare_info_png()
        if self.config.keep_metadata:
            info = self.info
        else:
            info = {}
            for key, val in self.info:
                if key in _SAVE_INFO_KEYS:
                    info[key] = val
        return MappingProxyType(info)
