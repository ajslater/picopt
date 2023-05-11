"""JPEG format."""
from copy import copy
from pathlib import Path
from typing import Optional

from PIL.JpegImagePlugin import JpegImageFile

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT_STR = JpegImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, False, False)
    PROGRAMS: dict[str, Optional[str]] = ImageHandler.init_programs(
        ("mozjpeg", "jpegtran")
    )
    _ARGS_PREFIX = ["-optimize", "-progressive", "-copy"]
    _MOZJPEG_ARGS_PREFIX = [PROGRAMS["mozjpeg"], *_ARGS_PREFIX]
    _JPEGTRAN_ARGS_PREFIX = [PROGRAMS["jpegtran"], *_ARGS_PREFIX]

    @classmethod
    def get_default_suffix(cls) -> str:
        """Override default suffix for jpeg."""
        return ".jpg"

    @classmethod
    def get_suffixes(cls, default_suffix: str) -> frozenset:
        """Initialize suffix instance variables."""
        return frozenset((default_suffix, "." + cls.OUTPUT_FORMAT_STR.lower()))

    def _jpegtran(self, args: list[str], old_path: Path, new_path: Path) -> Path:
        """Run the jpegtran type program."""
        args = copy(args)
        if not bin:
            return old_path
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        args += ["-outfile", str(new_path), str(old_path)]
        args_t = tuple(args)
        self.run_ext(args_t)
        return new_path

    def mozjpeg(self, old_path: Path, new_path: Path) -> Path:
        """Create argument list for mozjpeg."""
        return self._jpegtran(self._MOZJPEG_ARGS_PREFIX, old_path, new_path)

    def jpegtran(self, old_path: Path, new_path: Path) -> Path:
        """Create argument list for jpegtran."""
        return self._jpegtran(self._JPEGTRAN_ARGS_PREFIX, old_path, new_path)
