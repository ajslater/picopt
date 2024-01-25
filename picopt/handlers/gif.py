"""Gif format."""
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Optional

from PIL import Image
from PIL.GifImagePlugin import GifImageFile

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class Gif(ImageHandler):
    """GIF handler."""

    OUTPUT_FORMAT_STR = GifImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    PROGRAMS: MappingProxyType[str, Optional[str]] = ImageHandler.init_programs(
        ("gifsicle", "pil2gif")
    )
    _ARGS_PREFIX: tuple[Optional[str], ...] = (
        PROGRAMS.get("gifsicle", ""),
        "--optimize=3",
        "--batch",
    )

    def gifsicle(self, old_path: Path, new_path: Path) -> Path:
        """Return gifsicle args."""
        if not self._ARGS_PREFIX[0]:
            return old_path

        shutil.copy2(old_path, new_path)
        args = (*self._ARGS_PREFIX, str(new_path))
        self.run_ext(args)
        return new_path

    def pil2gif(self, old_path: Path, new_path: Path) -> Path:
        """Pillow gif optimization."""
        with Image.open(old_path) as image:
            image.save(new_path, self.OUTPUT_FORMAT_STR, optimize=True, save_all=True)
        image.close()  # for animated images
        return new_path


class AnimatedGif(Gif):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(Gif.OUTPUT_FORMAT_STR, True, True)
