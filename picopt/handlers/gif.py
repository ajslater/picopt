"""Gif format."""
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
    PIL2_KWARGS = MappingProxyType({"optimize": True, "save_all": True})
    _GIFSICLE_ARGS_PREFIX: tuple[str, ...] = ("--optimize=3", "--threads")

    def gifsicle(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Return gifsicle args."""
        opt_args = (*self._GIFSICLE_ARGS_PREFIX, "--output", str(new_path))
        args = (*exec_args, *opt_args, str(old_path))
        self.run_ext(args)
        return new_path


class GifAnimated(Gif):
    """Animated GIF handler."""

    OUTPUT_FILE_FORMAT = FileFormat(Gif.OUTPUT_FORMAT_STR, True, True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
