"""PNG format."""
import shutil

from copy import copy
from pathlib import Path
from typing import Tuple

from PIL import Image
from PIL.PngImagePlugin import PngImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import TIFF_FORMAT_OBJ, ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    BEST_ONLY: bool = False
    OUTPUT_FORMAT = PngImageFile.format
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, True, False)
    PROGRAMS: Tuple[str, ...] = ("pil2png", "optipng", "pngout")
    PREFERRED_PROGRAM: str = "optipng"
    _OPTIPNG_ARGS = ["optipng", "-o5", "-fix", "-force", "-quiet"]
    _PNGOUT_ARGS = ["pngout", "-q", "-force", "-y"]

    def optipng(self, old_path: Path, new_path: Path) -> Path:
        """Run the external program optipng on the file."""
        shutil.copy2(old_path, new_path)
        args = copy(self._OPTIPNG_ARGS)
        if self.config.destroy_metadata:
            args += ["-strip", "all"]
        args += [str(new_path)]
        self.run_ext(tuple(args))
        return new_path

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Pillow png optimization."""
        if (
            self.input_format not in set([TIFF_FORMAT_OBJ])
            or self.PREFERRED_PROGRAM not in self.config._available_programs
        ):
            # Optipng usually does a better job than Pillow
            new_path = old_path
        else:
            with Image.open(old_path) as image:
                image.save(
                    new_path,
                    self.OUTPUT_FORMAT,
                    optimize=True,
                    exif=self.metadata.exif,
                    icc_profile=self.metadata.icc_profile,
                )
        return new_path

    def pngout(self, old_path: Path, new_path: Path) -> Path:
        """Run the external program pngout on the file."""
        depth = png_bit_depth(old_path)
        if depth in (16, None):
            print(f"Skipped pngout for {depth} bit PNG:")
            result = old_path
        else:
            args = tuple(self._PNGOUT_ARGS + [str(old_path), str(new_path)])
            self.run_ext(args)
            result = new_path
        return result
