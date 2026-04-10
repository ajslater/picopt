"""
SVG format plugin.

Owns: SVG. Tool: svgo, either as a real binary or via npx.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from typing_extensions import override

from picopt.formats import SVG_FORMAT_STR, FileFormat
from picopt.plugins.base import (
    Detector,
    ExternalTool,
    Handler,
    ImageHandler,
    NpxTool,
    Plugin,
    Route,
    Tool,
)

if TYPE_CHECKING:
    from io import BytesIO

    from picopt.path import PathInfo

_SVGO_ARGS: tuple[str, ...] = ("--multipass", "--output", "-", "--input", "-")


class _SvgoMixin:
    """Shared run_stage so the binary and the npx variants share invocation."""

    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:  # noqa: ARG002
        return Handler.run_ext(
            (*self.exec_args(), *_SVGO_ARGS),  # pyright:ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            buf,
        )


class SvgoTool(_SvgoMixin, ExternalTool):
    """svgo installed as a global binary."""

    name = "svgo"
    binary = "svgo"


class NpxSvgoTool(_SvgoMixin, NpxTool):
    """svgo run via npx (no global install needed)."""

    name = "npx_svgo"
    npx_name = "svgo"


class SvgDetector(Detector):
    """SVG identification: just look at the suffix."""

    PRIORITY: int = 0

    @override
    @classmethod
    def identify(cls, path_info: PathInfo) -> FileFormat | None:
        return Svg.OUTPUT_FILE_FORMAT if path_info.suffix().lower() == ".svg" else None


class Svg(ImageHandler):
    """SVG handler."""

    OUTPUT_FORMAT_STR = SVG_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=True, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".svg",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((SvgoTool(), NpxSvgoTool()),)


PLUGIN = Plugin(
    name=SVG_FORMAT_STR,
    handlers=(Svg,),
    routes=(Route(file_format=Svg.OUTPUT_FILE_FORMAT, native=Svg),),
    detector=SvgDetector,
    default_enabled=False,
)
