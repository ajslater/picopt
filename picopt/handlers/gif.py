"""Gif format."""
import shutil

from pathlib import Path
from typing import Tuple

from PIL import Image
from PIL.GifImagePlugin import GifImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import ImageHandler


class Gif(ImageHandler):
    """GIF handler."""

    OUTPUT_FORMAT = GifImageFile.format
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, True, False)
    PROGRAMS: Tuple[str, ...] = ("gifsicle", "pil2gif")
    _ARGS_PREFIX = ["gifsicle", "--optimize=3", "--batch"]

    def gifsicle(self, old_path: Path, new_path: Path) -> Path:
        """Return gifsicle args."""
        shutil.copy2(old_path, new_path)
        args = tuple(self._ARGS_PREFIX + [str(new_path)])
        self.run_ext(args)
        return new_path

    def pil2gif(self, old_path: Path, new_path: Path) -> Path:
        """Pillow gif optimization."""
        with Image.open(old_path) as image:
            image.save(new_path, self.OUTPUT_FORMAT, optimize=True, save_all=True)
        return new_path


class AnimatedGif(Gif):
    """Animated GIF handler."""

    OUTPUT_FORMAT_OBJ = Format(Gif.OUTPUT_FORMAT, True, True)
