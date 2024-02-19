"""Methods for files that that can't be identified with PIL."""

from picopt.formats import FileFormat
from picopt.handlers.handler import Handler
from picopt.path import PathInfo


class NonPILIdentifier(Handler):
    """Methods for files that that can't be identified with PIL."""

    @classmethod
    def identify_format(
        cls,
        path_info: PathInfo,
    ) -> FileFormat | None:
        """Return the format if this handler can handle this path."""
        suffix = path_info.suffix().lower()
        if suffix == cls.get_default_suffix():
            return cls.OUTPUT_FILE_FORMAT
        return None
