"""Methods for files that that can't be identified with PIL."""

from picopt.formats import FileFormat
from picopt.handlers.handler import Handler
from picopt.path import PathInfo


class NonPILIdentifier(Handler):
    """Methods for files that that can't be identified with PIL."""

    INPUT_FILE_FORMAT = FileFormat("UNIMPLEMENTED")

    @classmethod
    def identify_format(
        cls,
        path_info: PathInfo,
    ) -> FileFormat | None:
        """Return the format if the suffix matches the handler."""
        # inefficient
        suffixes = cls.SUFFIXES if cls.SUFFIXES else "." + cls.OUTPUT_FORMAT_STR.lower()
        suffix = path_info.suffix().lower()
        if suffix in suffixes:
            return cls.INPUT_FILE_FORMAT
        return None
