"""JPEG format."""
import copy

from pathlib import Path

from PIL.JpegImagePlugin import JpegImageFile

from picopt.handlers.handler import Format
from picopt.handlers.image import ImageHandler


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT = JpegImageFile.format
    OUTPUT_FORMAT_OBJ = Format(OUTPUT_FORMAT, False, False)
    PROGRAMS: tuple[str, ...] = ("mozjpeg", "jpegtran")
    _ARGS_PREFIX = ["-optimize", "-progressive"]

    @classmethod
    def _output_suffix(cls) -> str:
        """JPEG suffix does not match format."""
        return "jpg"

    def _jpegtran(self, exe: str, old_path: Path, new_path: Path) -> Path:
        """Run the jpegtran type program."""
        args = [exe] + copy.copy(self._ARGS_PREFIX)
        if self.config.keep_metadata:
            args += ["-copy", "all"]
        else:
            args += ["-copy", "none"]
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
