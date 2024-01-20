"""WebP format."""
from pathlib import Path
from types import MappingProxyType

from picopt.handlers.handler import FileFormat
from picopt.handlers.image import ImageHandler


class SVG(ImageHandler):
    """SVG format class."""

    OUTPUT_FORMAT_STR = "SVG"
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, True)
    INPUT_FORMAT_SUFFIX = "." + OUTPUT_FORMAT_STR.lower()
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS: MappingProxyType[
        str, str | tuple[str, ...] | None
    ] = ImageHandler.init_programs(("svgo", "npx_svgo"))
    PREFERRED_PROGRAM = "svgo"
    _ARGS = ("--multipass",)

    def _svgo(self, old_path: Path, new_path: Path, program: tuple[str, ...]) -> Path:
        """Optimize using svgo."""
        args = (
            *program,
            *self._ARGS,
            "--input",
            str(old_path),
            "--output",
            str(new_path),
        )
        self.run_ext(args)
        return new_path

    def svgo(self, old_path: Path, new_path: Path) -> Path:
        """Svgo executable."""
        program: tuple[str, ...] = (self.PROGRAMS["svgo"],)  # type: ignore
        return self._svgo(old_path, new_path, program)

    def npx_svgo(self, old_path: Path, new_path: Path) -> Path:
        """Npx installed svgo."""
        program: tuple[str, ...] = self.PROGRAMS["npx_svgo"]  # type: ignore
        return self._svgo(old_path, new_path, program)
