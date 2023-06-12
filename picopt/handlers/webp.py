"""WebP format."""
from abc import ABC
from pathlib import Path
from typing import Any, Optional

from PIL import Image
from PIL.WebPImagePlugin import WebPImageFile

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import (
    CONVERTABLE_FILE_FORMATS,
    TIFF_FILE_FORMAT,
    ImageHandler,
)
from picopt.handlers.png import Png


class WebPBase(ImageHandler, ABC):
    """Base for handlers that use WebP utility commands."""

    PIL2WEBP_KWARGS: dict[str, Any] = {"lossless": True, "quality": 100, "method": 6}
    PIL2_ARGS: dict[str, Any] = PIL2WEBP_KWARGS

    def get_metadata_args(self) -> list[str]:
        """Get webp utility metadata args."""
        args = ["-metadata"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        return args

    def pil2webp(self, old_path: Path, new_path: Path) -> Path:
        """Pillow webp optimization."""
        return self.pil2native(old_path, new_path)


class WebP(WebPBase, ABC):
    """WebP format class."""

    OUTPUT_FORMAT_STR = WebPImageFile.format
    PROGRAMS: dict[str, Optional[str]] = WebPBase.init_programs(("cwebp",))
    ARGS_PREFIX = [
        PROGRAMS["cwebp"],
        "-mt",
        "-sharp_yuv",
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
    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, True, False)
    PREFERRED_PROGRAM: str = "cwebp"
    PROGRAMS: dict[str, Optional[str]] = {
        "pil2png": None,
        **WebP.PROGRAMS,
        "pil2webp": None,
    }
    ARGS_PREFIX = [*WebP.ARGS_PREFIX, "-lossless", "-q", "100", "-m", "6"]
    _PIL2PNG_FILE_FORMATS = CONVERTABLE_FILE_FORMATS | {TIFF_FILE_FORMAT}

    def pil2png(self, old_path: Path, new_path: Path) -> Path:
        """Internally convert unhandled formats to uncompressed png for cwebp."""
        if (
            self.input_file_format in self._PIL2PNG_FILE_FORMATS
            and self.PREFERRED_PROGRAM in self.config.computed.available_programs
        ):
            new_path = new_path.with_suffix(Png.get_default_suffix())
            with Image.open(old_path) as image:
                image.save(
                    new_path,
                    Png.OUTPUT_FORMAT_STR,
                    compress_level=0,
                    exif=self.metadata.exif,
                    icc_profile=self.metadata.icc_profile,
                )
            image.close()
            self.input_file_format = Png.OUTPUT_FILE_FORMAT
        else:
            new_path = old_path
        return new_path


class WebPLossy(WebP):
    """Handle lossy webp images."""

    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, False, False)
    ARGS_PREFIX = [*WebP.ARGS_PREFIX, "-m", "6", "-pass", "10", "-af"]


class Gif2WebP(WebPBase):
    """Animated WebP format class.

    There are no easy animated WebP optimization tools. So this only
    converts animated gifs.
    """

    OUTPUT_FORMAT_STR = WebP.OUTPUT_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WebP.OUTPUT_FORMAT_STR, True, True)
    PIL2WEBP_KWARGS: dict[str, Any] = {
        **WebPLossless.PIL2WEBP_KWARGS,
        "minimize_size": True,
    }
    PREFERRED_PROGRAM = "gif2webp"
    PROGRAMS: dict[str, Optional[str]] = WebPBase.init_programs(
        ("gif2webp", "pil2webp")
    )
    _ARGS_PREFIX = [
        PROGRAMS["gif2webp"],
        "-mixed",
        "-min_size",
        "-m",
        "6",
        "-mt",
    ]

    @classmethod
    def native_input_file_formats(cls):
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
