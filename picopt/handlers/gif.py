"""Gif format."""
import shutil
from pathlib import Path
from types import MappingProxyType

from PIL import Image
from PIL.GifImagePlugin import GifImageFile

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class Gif(ImageHandler):
    """GIF handler."""

    OUTPUT_FORMAT_STR = GifImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS: MappingProxyType[str, str | None] = ImageHandler.init_programs(
        ("gifsicle", "pil2gif")
    )
    _ARGS_PREFIX: tuple[str | None, ...] = (
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


class GifAnimated(Gif):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(Gif.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
