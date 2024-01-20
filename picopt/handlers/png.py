"""PNG format."""
from pathlib import Path
from types import MappingProxyType

from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.handlers.convertible import CONVERTABLE_FORMAT_STRS, GIF_FORMAT_STR
from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler
from picopt.pillow.png_bit_depth import png_bit_depth


class Png(ImageHandler):
    """PNG format class."""

    BEST_ONLY: bool = False
    OUTPUT_FORMAT_STR = PngImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    CONVERT_FROM_FORMAT_STRS = frozenset(CONVERTABLE_FORMAT_STRS | {GIF_FORMAT_STR})
    PIL2_ARGS: MappingProxyType[str, bool] = MappingProxyType({"optimize": True})
    PROGRAMS: MappingProxyType[
        str, str | tuple[str, ...] | None
    ] = ImageHandler.init_programs(("pil2png", "oxipng", "pngout"))
    PREFERRED_PROGRAM: str = "oxipng"
    _OXIPNG_ARGS: tuple[str | None, ...] = (
        PROGRAMS["oxipng"],
        "--opt",
        "5",
        "--alpha",
        "--fix",
        "--force",
        "--zopfli",
    )
    _PNGOUT_ARGS: tuple[str | None, ...] = (PROGRAMS["pngout"], "-force", "-y")

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Pillow png optimization."""
        return self.pil2native(old_path, new_path)

    def oxipng(self, old_path: Path, new_path: Path) -> Path:
        """Run the external program oxipng on the file."""
        args_l = list(self._OXIPNG_ARGS)
        if not self.config.keep_metadata:
            args_l += ["--strip", "safe"]
        args_l += ["--out", str(new_path), str(old_path)]
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
