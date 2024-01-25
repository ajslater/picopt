"""Gif format."""
import shutil
from pathlib import Path
from types import MappingProxyType

from PIL.GifImagePlugin import GifImageFile

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class Gif(ImageHandler):
    """GIF handler."""

    OUTPUT_FORMAT_STR = GifImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("gifsicle", "pil2native"),)
    _GIFSICLE_ARGS_PREFIX: tuple[str | None, ...] = (
        "--optimize=3",
        "--batch",
    )
    PIL2_ARGS = MappingProxyType({"optimize": True, "save_all": True})

    def gifsicle(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Return gifsicle args."""
        if not self._GIFSICLE_ARGS_PREFIX[0]:
            return old_path

        shutil.copy2(old_path, new_path)
        args = (*exec_args, *self._GIFSICLE_ARGS_PREFIX, str(new_path))
        self.run_ext(args)
        return new_path


class GifAnimated(Gif):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(Gif.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
