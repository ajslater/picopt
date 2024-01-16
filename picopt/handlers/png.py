"""PNG format."""
from pathlib import Path
from types import MappingProxyType
from typing import Optional

from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    BEST_ONLY: bool = False
    OUTPUT_FORMAT_STR = PngImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    PIL2_ARGS: MappingProxyType[str, bool] = MappingProxyType({"optimize": True})
    PROGRAMS: MappingProxyType[str, Optional[str]] = ImageHandler.init_programs(
        ("pil2png", "optipng", "pngout")
    )
    PREFERRED_PROGRAM: str = "optipng"
    _OPTIPNG_ARGS: tuple[Optional[str], ...] = (
        PROGRAMS["optipng"],
        "-o5",
        "-fix",
        "-force",
    )
    _PNGOUT_ARGS: tuple[Optional[str], ...] = (PROGRAMS["pngout"], "-force", "-y")

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Pillow png optimization."""
        return self.pil2native(old_path, new_path)

    def optipng(self, old_path: Path, new_path: Path) -> Path:
        """Run the external program optipng on the file."""
        args_l = list(self._OPTIPNG_ARGS)
        if not self.config.keep_metadata:
            args_l += ["-strip", "all"]
        args_l += ["-out", str(new_path), str(old_path)]
        self.run_ext(tuple(args_l))
        return new_path

    def pngout(self, old_path: Path, new_path: Path) -> Path:
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
            args = (*self._PNGOUT_ARGS, str(old_path), str(new_path))
            self.run_ext(args)
            result = new_path
        return result
