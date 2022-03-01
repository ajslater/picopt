"""WebP format."""
from abc import ABC
from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image
from PIL.WebPImagePlugin import WebPImageFile

from picopt.handlers.gif import Gif
from picopt.handlers.handler import Format
from picopt.handlers.image import CONVERTABLE_FORMATS, ImageHandler
from picopt.handlers.png import Png


class WebP(ImageHandler, ABC):
    """WebP format class."""

    FORMAT_STR = WebPImageFile.format
    SUFFIX: str = "." + FORMAT_STR.lower()
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
        args = tuple(self.ARGS_PREFIX + [str(old_path), "-o", str(new_path)])
        self.run_ext(args)
        return new_path


class WebPLossless(WebP):
    """Handle lossless webp images and images that convert to lossless webp."""

    FORMAT = Format(WebP.FORMAT_STR, True, False)
    NATIVE_FORMATS = set((FORMAT,))
    PROGRAMS: Tuple[str, ...] = ("pil2png", *WebP.PROGRAMS, "pil2webp")
    ARGS_PREFIX = WebP.ARGS_PREFIX + [
        "-lossless",
        "-z",
        "9",
    ]
    PIL2WEBP_KWARGS: Dict[str, Any] = {"lossless": True, "quality": 100, "method": 6}
    BEST_ONLY = False

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Internally convert uncompressed formats to uncompressed png."""
        if (
            self.format in CONVERTABLE_FORMATS
            and "cwebp" in self.config._available_programs
        ):
            new_path = new_path.with_suffix(Png.SUFFIX)
            with Image.open(old_path) as image:
                image.save(new_path, "PNG", compress_level=0)
            self.format = Png.FORMAT
        else:
            new_path = old_path
        return new_path

    def pil2webp(self, old_path: Path, new_path: Path) -> Path:
        """Pillow webp optimization."""
        if "cwebp" in self.config._available_programs:
            new_path = old_path
        else:
            with Image.open(old_path) as image:
                if self.config.destroy_metadata:
                    exif = None
                else:
                    exif = image.info.get("exif")
                image.save(new_path, self.FORMAT_STR, **self.PIL2WEBP_KWARGS, exif=exif)
        return new_path


class WebPLossy(WebP):
    """Handle lossy webp images."""

    FORMAT = Format(WebP.FORMAT_STR, False, False)
    NATIVE_FORMATS = set((FORMAT,))
    ARGS_PREFIX = WebP.ARGS_PREFIX + [
        "-m",
        "6",
        "-pass",
        "10",
    ]


class Gif2WebP(ImageHandler):
    """
    Animated WebP format class.

    There are no easy animated WebP optimization tools. So this only
    converts animated gifs.
    """

    FORMAT_STR = Gif.FORMAT_STR
    SUFFIX = WebP.SUFFIX
    PROGRAMS: Tuple[str, ...] = ("gif2webp", "pil2webp")
    _ARGS_PREFIX = [
        "gif2webp",
        "-mixed",
        "-min_size",
        "-m",
        "6",
        "-mt",
    ]
    PIL2WEBP_KWARGS: Dict[str, Any] = {
        **WebPLossless.PIL2WEBP_KWARGS,
        "minimize_size": True,
    }

    def gif2webp(self, old_path: Path, new_path: Path) -> Path:
        """Convert animated gif to animated webp."""
        args = tuple(self._ARGS_PREFIX + [str(old_path), "-o", str(new_path)])
        self.run_ext(args)
        return new_path

    def pil2webp(self, old_path: Path, new_path: Path) -> Path:
        """Pillow webp optimization."""
        if "gif2webp" in self.config._available_programs:
            new_path = old_path
        else:
            with Image.open(old_path) as image:
                if self.config.destroy_metadata:
                    exif = None
                else:
                    exif = image.info.get("exif")
                image.save(new_path, "WEBP", **self.PIL2WEBP_KWARGS, exif=exif)
        return new_path
