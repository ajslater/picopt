"""JPEG format."""
from pathlib import Path

from PIL.JpegImagePlugin import JpegImageFile

from picopt.formats import FileFormat
from picopt.handlers.image import ImageHandler


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT_STR = JpegImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("mozjpeg", "jpegtran"),)
    _JPEGTRAN_ARGS_PREFIX = ("-optimize", "-progressive")
    # PIL Cannot save jpegs losslessly

    @classmethod
    def get_default_suffix(cls) -> str:
        """Override default suffix for jpeg."""
        return ".jpg"

    @classmethod
    def get_suffixes(cls, default_suffix: str) -> frozenset:
        """Initialize suffix instance variables."""
        return frozenset((default_suffix, "." + cls.OUTPUT_FORMAT_STR.lower()))

    def _jpegtran(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Run the jpegtran type program."""
        args = [*exec_args, *self._JPEGTRAN_ARGS_PREFIX]
        args += ["-copy"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        args += ["-outfile", str(new_path), str(old_path)]
        self.run_ext(tuple(args))
        return new_path

    def mozjpeg(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Create argument list for mozjpeg."""
        return self._jpegtran(exec_args, old_path, new_path)

    def jpegtran(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Create argument list for jpegtran."""
        return self._jpegtran(exec_args, old_path, new_path)
