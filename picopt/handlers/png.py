"""PNG format."""
from pathlib import Path
from types import MappingProxyType
from typing import Any

import oxipng
from PIL.GifImagePlugin import GifImageFile
from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.formats import CONVERTIBLE_FORMAT_STRS, FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    OUTPUT_FORMAT_STR = PngImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS = frozenset(
        CONVERTIBLE_FORMAT_STRS | {GifImageFile.format}
    )
    PROGRAMS = (
        ("pil2png",),
        ("internal_oxipng",),
        ("pngout",),
    )
    _OXIPNG_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {
            "level": 5,
            "fix_errors": True,
            "force": True,
            "optimize_alpha": True,
            "deflate": oxipng.Deflaters.zopfli(15),
        }
    )
    _PNGOUT_ARGS: tuple[str, ...] = ("-force", "-y")

    def internal_oxipng(
        self,
        exec_args: tuple[str, ...],  # noqa: ARG002
        old_path: Path,
        new_path: Path,
    ):
        """Run internal oxipng on the file."""
        opts = {**self._OXIPNG_KWARGS}
        if not self.config.keep_metadata:
            opts["strip"] = oxipng.StripChunks.safe()
        oxipng.optimize(old_path, output=new_path, **opts)
        return new_path

    def pngout(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Run the external program pngout on the file."""
        depth = png_bit_depth(old_path)
        if depth in (16, None):
            cprint(
                f"Skipped pngout for {depth} bit PNG: {old_path}",
                "white",
                attrs=["dark"],
            )
            result = old_path
        else:
            args = (*exec_args, *self._PNGOUT_ARGS, str(old_path), str(new_path))
            self.run_ext(args)
            result = new_path
        return result
