"""WebP format."""
from abc import ABC
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image
from PIL.WebPImagePlugin import WebPImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import CONVERTABLE_FORMAT_OBJS, TIFF_FORMAT_OBJ, ImageHandler
from picopt.handlers.png import Png


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PREFERRED_PROGRAM: str = ""
    PIL2WEBP_KWARGS: Dict[str, Any] = {"lossless": True, "quality": 100, "method": 6}

    def get_metadata_args(self) -> List[str]:
        """Get webp utility metadata args."""
        args = ["-metadata"]
        if self.config.destroy_metadata:
            args += ["none"]
        else:
            args += ["all"]
        return args

    def pil2webp(self, old_path: Path, new_path: Path) -> Path:
        """Pillow webp optimization."""
        if (
            self.PREFERRED_PROGRAM in self.config._available_programs
            and self.input_format != TIFF_FORMAT_OBJ
        ):
            new_path = old_path
        else:
            with Image.open(old_path) as image:
                image.save(
                    new_path,
                    self.OUTPUT_FORMAT,
                    **self.PIL2WEBP_KWARGS,
                    exif=self.metadata.exif,
                    icc_profile=self.metadata.icc_profile
                )
        return new_path


class WebP(WebPBase, ABC):
    """WebP format class."""

    OUTPUT_FORMAT = WebPImageFile.format
    PROGRAMS: Tuple[str, ...] = ("cwebp",)
    ARGS_PREFIX = [
        "cwebp",
        "-mt",
        "-quiet",
        "-sharp_yuv",
        "-af",
        "-alpha_filter",
        "best",
    ]

    def cwebp(self, old_path: Path, new_path: Path) -> Path:
        """Optimize using cwebp."""
        args = tuple(
            self.ARGS_PREFIX
            + self.get_metadata_args()
            + [str(old_path), "-o", str(new_path)]
        )
        self.run_ext(args)
        return new_path


class WebPLossless(WebP):
    """Handle lossless webp images and images that convert to lossless webp."""

    BEST_ONLY: bool = False
    OUTPUT_FORMAT_OBJ = Format(WebP.OUTPUT_FORMAT, True, False)
    PREFERRED_PROGRAM: str = "cwebp"
    PROGRAMS: Tuple[str, ...] = ("pil2png", *WebP.PROGRAMS, "pil2webp")
    ARGS_PREFIX = WebP.ARGS_PREFIX + [
        "-lossless",
        "-z",
        "9",
    ]

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Internally convert uncompressed formats to uncompressed png."""
        if (
            self.input_format in (CONVERTABLE_FORMAT_OBJS | set([TIFF_FORMAT_OBJ]))
            and self.PREFERRED_PROGRAM in self.config._available_programs
        ):
            new_path = new_path.with_suffix(Png.output_suffix())
            with Image.open(old_path) as image:
                image.save(
                    new_path,
                    Png.OUTPUT_FORMAT,
                    compress_level=0,
                    exif=self.metadata.exif,
                    icc_profile=self.metadata.icc_profile,
                )
            self.input_format = Png.OUTPUT_FORMAT_OBJ
        else:
            new_path = old_path
        return new_path


class WebPLossy(WebP):
    """Handle lossy webp images."""

    OUTPUT_FORMAT_OBJ = Format(WebP.OUTPUT_FORMAT, False, False)
    ARGS_PREFIX = WebP.ARGS_PREFIX + [
        "-m",
        "6",
        "-pass",
        "10",
    ]


class Gif2WebP(WebPBase):
    """
    Animated WebP format class.

    There are no easy animated WebP optimization tools. So this only
    converts animated gifs.
    """

    OUTPUT_FORMAT = WebP.OUTPUT_FORMAT
    OUTPUT_FORMAT_OBJ = Format(WebP.OUTPUT_FORMAT, True, True)
    PIL2WEBP_KWARGS: Dict[str, Any] = {
        **WebPLossless.PIL2WEBP_KWARGS,
        "minimize_size": True,
    }
    PREFERRED_PROGRAM = "gif2webp"
    PROGRAMS: Tuple[str, ...] = ("gif2webp", "pil2webp")
    _ARGS_PREFIX = [
        "gif2webp",
        "-mixed",
        "-min_size",
        "-m",
        "6",
        "-mt",
    ]

    @classmethod
    def native_input_formats(cls):
        """No native formats."""
        return set()

    def gif2webp(self, old_path: Path, new_path: Path) -> Path:
        """Convert animated gif to animated webp."""
        args = tuple(
            self._ARGS_PREFIX
            + self.get_metadata_args()
            + [str(old_path), "-o", str(new_path)]
        )
        self.run_ext(args)
        return new_path
