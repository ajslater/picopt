"""PNG format."""
from copy import copy
from pathlib import Path
from typing import Optional

from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.handlers.handler import Format
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    BEST_ONLY: bool = False
    OUTPUT_FORMAT = PngImageFile.format
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, True, False)
    PIL2_ARGS: dict[str, bool] = {"optimize": True}
    PROGRAMS: dict[str, Optional[str]] = ImageHandler.init_programs(
        ("pil2png", "optipng", "pngout")
    )
    PREFERRED_PROGRAM: str = "optipng"
    _OPTIPNG_ARGS = [PROGRAMS["optipng"], "-o5", "-fix", "-force"]
    _PNGOUT_ARGS = [PROGRAMS["pngout"], "-force", "-y"]

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Pillow png optimization."""
        return self.pil2native(old_path, new_path)

    def optipng(self, old_path: Path, new_path: Path) -> Path:
        """Run the external program optipng on the file."""
        args = copy(self._OPTIPNG_ARGS)
        if not self.config.keep_metadata:
            args += ["-strip", "all"]
        args += ["-out", str(new_path), str(old_path)]
        self.run_ext(tuple(args))
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
            args = tuple(self._PNGOUT_ARGS + [str(old_path), str(new_path)])
            self.run_ext(args)
            result = new_path
        return result
