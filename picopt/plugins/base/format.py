"""
File format dataclass.

Format-specific knowledge (which strings are lossless, which are convertible
from PIL, etc) lives in the individual plugin modules under picopt/plugins/
and is exposed via the plugin registry.
"""

from dataclasses import dataclass

from typing_extensions import override


@dataclass(eq=True, frozen=True)
class FileFormat:
    """A file format, with image attributes."""

    format_str: str
    lossless: bool = True
    animated: bool = False
    archive: bool = False

    @override
    def __repr__(self) -> str:
        """Represent format as a string."""
        parts = [self.format_str]
        if self.archive:
            parts.append("archive")
        else:
            parts.append("lossless" if self.lossless else "lossy")
            if self.animated:
                parts.append("animated")
        return " ".join(parts)


# A handful of well-known string keys that are referenced from non-plugin code.
# Plugins import these, but the values are kept here so the registry doesn't
# have to special-case anything.
PNGINFO_XMP_KEY = "XML:com.adobe.xmp"
SVG_FORMAT_STR = "SVG"
