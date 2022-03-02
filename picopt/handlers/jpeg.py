"""JPEG format."""
import copy

from pathlib import Path
from typing import Tuple

from PIL.JpegImagePlugin import JpegImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import ImageHandler


class Jpeg(ImageHandler):
    """JPEG format class."""

    FORMAT_STR = JpegImageFile.format
    FORMAT = Format(FORMAT_STR, False, False)
    NATIVE_FORMATS = set((FORMAT,))
    SUFFIX = ".jpg"
    PROGRAMS: Tuple[str, ...] = ("mozjpeg", "jpegtran")
    _ARGS_PREFIX = ["-optimize", "-progressive"]

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
