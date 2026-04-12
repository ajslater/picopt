"""Plugin base classes and descriptors."""

from picopt.plugins.base.animated import ImageAnimated
from picopt.plugins.base.archive import ArchiveHandler
from picopt.plugins.base.container import ContainerHandler
from picopt.plugins.base.format import PNGINFO_XMP_KEY, SVG_FORMAT_STR, FileFormat
from picopt.plugins.base.handler import Handler
from picopt.plugins.base.image import ImageHandler
from picopt.plugins.base.plugin import Detector, Plugin, Route
from picopt.plugins.base.tool import (
    ExternalTool,
    InternalTool,
    NpxTool,
    PILSaveTool,
    Tool,
    ToolStatus,
)

__all__ = (
    "PNGINFO_XMP_KEY",
    "SVG_FORMAT_STR",
    "ArchiveHandler",
    "ContainerHandler",
    "Detector",
    "ExternalTool",
    "FileFormat",
    "Handler",
    "ImageAnimated",
    "ImageHandler",
    "InternalTool",
    "NpxTool",
    "PILSaveTool",
    "Plugin",
    "Route",
    "Tool",
    "ToolStatus",
)
