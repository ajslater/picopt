"""JPEG format."""
import copy

from pathlib import Path
from typing import Tuple

from PIL import Image
from PIL.JpegImagePlugin import JpegImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import ImageHandler


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT = JpegImageFile.format
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, False, False)
    PROGRAMS: Tuple[str, ...] = ("mozjpeg", "jpegtran", "pil2jpeg")
    _ARGS_PREFIX = ["-optimize", "-progressive"]

    @classmethod
    def _output_suffix(cls) -> str:
        """JPEG suffix does not match format."""
        return "jpg"

    def _jpegtran(self, exe: str, old_path: Path, new_path: Path) -> Path:
        """Run the jpegtran type program."""
        args = [exe] + copy.copy(self._ARGS_PREFIX)
        if self.config.destroy_metadata:
            args += ["-copy", "none"]
        else:
            args += ["-copy", "all"]
        args += ["-outfile", str(new_path), str(old_path)]
        args_t = tuple(args)
        self.run_ext(args_t)
        return new_path

    def mozjpeg(self, old_path: Path, new_path: Path) -> Path:
        """Create argument list for mozjpeg."""
        return self._jpegtran("mozjpeg", old_path, new_path)

    def jpegtran(self, old_path: Path, new_path: Path) -> Path:
        """Create argument list for jpegtran."""
        return self._jpegtran("jpegtran", old_path, new_path)

    def pil2jpeg(self, old_path: Path, new_path: Path) -> Path:
        """Use Pillow to optimize JPEG."""
        with Image.open(old_path) as image:
            image.save(
                new_path,
                self.OUTPUT_FORMAT,
                optimize=True,
                progressive=True,
                exif=self.metadata.exif,
                icc_profile=self.metadata.icc_profile,
                quality=100,
                subsampling="keep",
            )
        return new_path
