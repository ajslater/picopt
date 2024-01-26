"""PNG format."""
from pathlib import Path
from types import MappingProxyType

from PIL.GifImagePlugin import GifImageFile
from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.handlers.convertible import CONVERTIBLE_FORMAT_STRS
from picopt.handlers.handler import FileFormat
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
    PIL2_KWARGS = MappingProxyType({"optimize": True})
    PROGRAMS = (
        ("pil2png",),
        ("oxipng", "optipng", "pil2native"),
        ("pngout",),
    )
    _OXIPNG_ARGS: tuple[str, ...] = (
        "--opt",
        "5",
        "--alpha",
        "--fix",
        "--force",
        "--zopfli",
    )
    _OPTIPNG_ARGS: tuple[str, ...] = ("-o5", "-fix", "-force")
    _PNGOUT_ARGS: tuple[str, ...] = ("-force", "-y")

    def oxipng(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Run the external program oxipng on the file."""
        args = [*exec_args, *self._OXIPNG_ARGS]
        if not self.config.keep_metadata:
            args += ["--strip", "safe"]
        args += ["--out", str(new_path), str(old_path)]
        self.run_ext(tuple(args))
        return new_path

    def optipng(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Run the external program optipng on the file."""
        args = [*exec_args, *self._OPTIPNG_ARGS]
        if not self.config.keep_metadata:
            args += ["-strip", "all"]
        args += ["-out", str(new_path), str(old_path)]
        self.run_ext(tuple(args))
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
