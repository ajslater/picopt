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
    PROGRAMS: MappingProxyType[str, str | None] = ImageHandler.init_programs(("svgo",))
    ARGS_PREFIX = (PROGRAMS["svgo"], "--multipass")

    def svgo(self, old_path: Path, new_path: Path) -> Path:
        """Optimize using svgo."""
        args = (
            *self.ARGS_PREFIX,
            "--input",
            str(old_path),
            "--output",
            str(new_path),
        )
        self.run_ext(args)
        return new_path
