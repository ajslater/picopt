"""WebP format."""
from pathlib import Path

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class SVG(ImageHandler):
    """SVG format class."""

    OUTPUT_FORMAT_STR = "SVG"
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True)
    INPUT_FORMAT_SUFFIX = "." + OUTPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("svgo", "npx_svgo"),)
    _SVGO_ARGS = ("--multipass",)

    def _svgo(self, exec_args: tuple[str, ...], old_path: Path, new_path: Path) -> Path:
        """Optimize using svgo."""
        args = (
            *exec_args,
            *self._SVGO_ARGS,
            "--input",
            str(old_path),
            "--output",
            str(new_path),
        )
        self.run_ext(args)
        return new_path

    def svgo(self, exec_args: tuple[str, ...], old_path: Path, new_path: Path) -> Path:
        """Svgo executable."""
        return self._svgo(exec_args, old_path, new_path)

    def npx_svgo(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Npx installed svgo."""
        return self._svgo(exec_args, old_path, new_path)
