"""
WebP external tools.

The cwebp version probe (the old ``config/cwebp.py``) is folded into
:class:`CWebPTool`. On :meth:`CWebPTool.probe`, the tool parses cwebp's
version and records whether it is modern on the probed instance.
:class:`~picopt.plugins.webp.static.WebPLossless` and
:class:`~picopt.plugins.webp.animated.Img2WebPAnimatedLossless` read
:data:`CWEBP_TOOL`'s flag in ``__init__`` to widen their accepted input
formats (skipping the intermediate PNG round-trip for PPM/TIFF).
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC
from io import BytesIO
from pathlib import Path
from tempfile import mkstemp
from typing import BinaryIO

from typing_extensions import override

from picopt.plugins.base import ExternalTool, Handler, ToolStatus


def run_disk_input_tool(
    handler: Handler,
    buf: BinaryIO,
    args: tuple[str, ...],
) -> BinaryIO:
    """
    Drive an external tool that needs a real input file path.

    cwebp and gif2webp don't accept stdin. If ``buf`` is already a
    BufferedReader on a real file we use that file's path; otherwise we
    spill the buffer to a tmp file under the working directory.
    """
    is_tmp = isinstance(buf, BytesIO)
    if is_tmp:
        wp = handler.get_working_path()
        fd, tmp_str = mkstemp(prefix=wp.name + ".", suffix=handler.output_suffix)
        os.close(fd)
        input_path: Path | None = Path(tmp_str)
    else:
        input_path = handler.path_info.path
    if input_path is None:
        msg = "No input path available for external WebP tool"
        raise ValueError(msg)
    full_args = (*args, str(input_path))
    return handler.run_ext_fs(full_args, buf, input_path, input_path_tmp=is_tmp)


def hash_tmp_dir_suffix(handler: Handler) -> str:
    """Unique-ish tmpdir suffix derived from the handler's working path."""
    wp = handler.get_working_path()
    return f"{hash(str(wp.parent))}-{wp.name}"


class CWebPTool(ExternalTool):
    """
    The ``cwebp`` external still encoder.

    Probing records on the instance whether PPM/TIFF can be passed in
    directly. The doctor command will see this tool listed under
    WebPLossless's PIPELINE.
    """

    name = "cwebp"
    binary = "cwebp"
    version_args = ("-version",)
    # cwebp before this version only accepts PNG and WebP as input formats.
    # Newer cwebps accept PPM and TIFF as well, which lets us skip the
    # intermediate PNG round-trip when picopt is converting from those.
    _MIN_CWEBP_VERSION: tuple[int, int, int] = (1, 2, 3)

    def __init__(self) -> None:
        """Default to legacy so a missing cwebp never widens input formats."""
        super().__init__()
        self.is_modern: bool = False

    @staticmethod
    def _parse_cwebp_version(version_str: str) -> tuple[int, ...]:
        """Parse '1.3.2' or '1.3.2 libwebp 1.3.2' into a tuple of ints."""
        if not version_str:
            return ()
        head = version_str.split(maxsplit=1)[0]
        parts: list[int] = []
        for part in head.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                break
        return tuple(parts)

    @override
    def _probe(self) -> ToolStatus:
        status = super()._probe()
        if status.available:
            parsed = CWebPTool._parse_cwebp_version(status.version)
            self.is_modern = bool(parsed) and parsed >= CWebPTool._MIN_CWEBP_VERSION
        return status

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        # Duck-typed: any handler exposing cwebp_args() qualifies. Keeps
        # the tool layer from importing handler classes (import cycle).
        cwebp_args = getattr(handler, "cwebp_args", None)
        if cwebp_args is None:
            msg = f"CWebPTool cannot run on {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *cwebp_args())
        return run_disk_input_tool(handler, buf, args)


# The shared, probed-once instance. WebPLossless's PIPELINE holds it, and
# both WebPLossless and Img2WebPAnimatedLossless read its ``is_modern``
# flag at handler construction time.
CWEBP_TOOL = CWebPTool()


class WebPExternalTool(ExternalTool, ABC):
    """WebP Tool Suite Tool."""

    version_args = ("-version",)

    @override
    def parse_version(self, version: str) -> str:
        """Version is last term."""
        version = super().parse_version(version)
        return version.split()[-1]


class Gif2WebPTool(WebPExternalTool):
    """The ``gif2webp`` external animated-GIF encoder."""

    name = "gif2webp"
    binary = "gif2webp"

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        gif2webp_args = getattr(handler, "gif2webp_args", None)
        if gif2webp_args is None:
            msg = f"Gif2WebPTool cannot run on {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *gif2webp_args())
        return run_disk_input_tool(handler, buf, args)


class Img2WebPTool(WebPExternalTool):
    """
    The ``img2webp`` external animated-WebP packer.

    Implements ``run_pack`` rather than ``run_stage`` because img2webp's
    role is to assemble already-extracted frame files into the final
    animated WebP. The handler that owns this tool extracts frames to
    disk during ``walk()``; ``run_pack()`` reads the frame paths off the
    handler and shells out.
    """

    name = "img2webp"
    binary = "img2webp"

    @override
    def run_pack(self, handler: Handler) -> BinaryIO:
        img2webp_args = getattr(handler, "img2webp_args", None)
        if img2webp_args is None:
            msg = f"Img2WebPTool cannot pack {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *img2webp_args())
        proc = subprocess.run(args, check=True, capture_output=True)  # noqa: S603
        return BytesIO(proc.stdout)


class WebPMuxTool(ExternalTool):
    """
    The ``webpmux`` external animated-WebP demuxer + packer.

    Used for both unpacking (``webpmux -get frame N``) and packing
    (``webpmux -frame ... -loop 0``). The unpack side is invoked from the
    handler's overridden ``walk()``; the pack side is the standard
    ``run_pack`` entry point that the handler's ``pack_into`` calls.
    """

    name = "webpmux"
    binary = "webpmux"
    version_args = ("-version",)

    @override
    def run_pack(self, handler: Handler) -> BinaryIO:
        webpmux_pack_args = getattr(handler, "webpmux_pack_args", None)
        if webpmux_pack_args is None:
            msg = f"WebPMuxTool cannot pack {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *webpmux_pack_args())
        proc = subprocess.run(args, check=True, capture_output=True)  # noqa: S603
        return BytesIO(proc.stdout)
