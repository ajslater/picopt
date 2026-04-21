"""
WebP format plugin.

Owns: WebP (still + animated) plus the GIF→WebP and PNG→WebP conversion
routes. Consolidates the original::

    handlers/image/webp.py
    handlers/container/animated/webp.py
    handlers/container/animated/webpbase.py
    handlers/container/animated/webpmux.py
    handlers/container/animated/img2webp.py
    config/cwebp.py

into one file.

The five WebP handlers cover four different unpack/pack strategies for
the same output format. They are listed in ``Route.convert`` in preference
order; the registry/config layer probes each handler's ``PIPELINE`` and
the routing layer picks the first whose tools are all available.

- :class:`WebPLossless`              still WebP. Stages: optional
                                     PIL→PNG round-trip if input isn't
                                     already cwebp-acceptable, then
                                     cwebp (preferred) or PIL save.

- :class:`Gif2WebPAnimatedLossless`  animated GIF → animated WebP.
                                     This is an :class:`ImageHandler`,
                                     not a container — gif2webp consumes
                                     the entire animated GIF in one shot.

- :class:`Img2WebPAnimatedLossless`  container. Frames are written to
                                     disk as lossless WebP via Pillow at
                                     unpack time, then ``img2webp`` packs
                                     the frame files.

- :class:`WebPMuxAnimatedLossless`   container. ``webpmux -get frame``
                                     extracts frames; ``webpmux -frame``
                                     packs them. Only valid for animated
                                     WebP input (webpmux can't read
                                     anything else).

- :class:`PILPackWebPAnimatedLossless`
                                     container. Pure-Pillow fallback
                                     using the inherited
                                     :class:`ImageAnimated` walk and
                                     ``Image.save(save_all=True)`` pack.
                                     Empty PIPELINE — Pillow is always
                                     available.

The cwebp version probe (the old ``config/cwebp.py``) is folded into
:class:`CWebPTool`. On its first :meth:`probe`, the tool parses cwebp's
version and sets the class attribute :attr:`CWebPTool.IS_MODERN_CWEBP`.
:class:`WebPLossless` and :class:`Img2WebPAnimatedLossless` widen their
``_input_file_formats`` to accept PPM/TIFF directly when that flag is set,
which lets them skip the intermediate PNG round-trip.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from abc import ABC
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
from tempfile import mkdtemp, mkstemp
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, BinaryIO

from PIL.WebPImagePlugin import WebPImageFile
from typing_extensions import override

from picopt.path import PathInfo
from picopt.plugins.base import (
    ExternalTool,
    Handler,
    ImageAnimated,
    ImageHandler,
    PILSaveTool,
    Plugin,
    Route,
    Tool,
    ToolStatus,
)
from picopt.plugins.base.format import FileFormat
from picopt.plugins.gif import Gif, GifAnimated
from picopt.plugins.png import Png, PngAnimated

# cwebp >= 1.2.3 accepts PPM and TIFF input directly. Older releases need a
# pre-conversion. CWebPTool.probe() detects the version once and stores the
# result on CWebPTool.IS_MODERN_CWEBP; handlers that benefit widen their
# accepted input formats with these entries in __init__.
_PPM_FILE_FORMAT = FileFormat("PPM", lossless=True, animated=False)
_TIFF_FILE_FORMAT = FileFormat("TIFF", lossless=True, animated=False)
MODERN_CWEBP_FORMATS: frozenset[FileFormat] = frozenset(
    {_PPM_FILE_FORMAT, _TIFF_FILE_FORMAT}
)
if TYPE_CHECKING:
    from collections.abc import Generator


_WEBP_FORMAT_STR: str = str(WebPImageFile.format)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _run_disk_input_tool(
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


def _hash_tmp_dir_suffix(handler: Handler) -> str:
    wp = handler.get_working_path()
    return f"{hash(str(wp.parent))}-{wp.name}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class CWebPTool(ExternalTool):
    """
    The ``cwebp`` external still encoder.

    Probing it has the side effect of telling :class:`WebPLossless` whether
    PPM/TIFF can be passed in directly. The doctor command will see this
    tool listed under WebPLossless's PIPELINE.
    """

    name = "cwebp"
    binary = "cwebp"
    version_args = ("-version",)
    # Set by CWebPTool.probe(). Default False so that the (rare) case of
    # cwebp being missing entirely doesn't accidentally widen the input
    # format set.
    # cwebp before this version only accepts PNG and WebP as input formats.
    # Newer cwebps accept PPM and TIFF as well, which lets us skip the
    # intermediate PNG round-trip when picopt is converting from those.
    _MIN_CWEBP_VERSION: tuple[int, int, int] = (1, 2, 3)
    IS_MODERN_CWEBP: bool = False

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
    def probe(self) -> ToolStatus:
        status = super().probe()
        if status.available:
            parsed = CWebPTool._parse_cwebp_version(status.version)
            # Set on class
            CWebPTool.IS_MODERN_CWEBP = (
                bool(parsed) and parsed >= CWebPTool._MIN_CWEBP_VERSION
            )
        return status

    @override
    def run_stage(self, handler: Handler, buf: BinaryIO) -> BinaryIO:
        if not isinstance(handler, WebPLossless):
            msg = f"CWebPTool cannot run on {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *handler.cwebp_args())
        return _run_disk_input_tool(handler, buf, args)


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
        if not isinstance(handler, Gif2WebPAnimatedLossless):
            msg = f"Gif2WebPTool cannot run on {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *handler.gif2webp_args())
        return _run_disk_input_tool(handler, buf, args)


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
        if not isinstance(handler, Img2WebPAnimatedLossless):
            msg = f"Img2WebPTool cannot pack {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *handler.img2webp_args())
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
        if not isinstance(handler, WebPMuxAnimatedLossless):
            msg = f"WebPMuxTool cannot pack {type(handler).__name__}"
            raise TypeError(msg)
        args = (*self.exec_args(), *handler.webpmux_pack_args())
        proc = subprocess.run(args, check=True, capture_output=True)  # noqa: S603
        return BytesIO(proc.stdout)


# ---------------------------------------------------------------------------
# Still WebP
# ---------------------------------------------------------------------------


class WebPLossless(ImageHandler):
    """Lossless still WebP handler."""

    OUTPUT_FORMAT_STR = _WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(_WEBP_FORMAT_STR, lossless=True, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT, Png.OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".webp",)

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"quality": 100, "method": 6, "lossless": True}
    )

    # Tier 1: convert non-acceptable inputs to PNG via Pillow. If the input
    #         is already in INPUT_FILE_FORMATS this is a no-op (pil_save
    #         short-circuits when self.input_file_format is acceptable).
    # Tier 2: encode to WebP. cwebp wins when available; otherwise Pillow
    #         saves directly to WebP.
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (
            PILSaveTool(
                target_format_str="PNG",
                save_kwargs={"compress_level": 0},
                name="pil2png",
            ),
        ),
        (
            CWebPTool(),
            PILSaveTool(target_format_str=_WEBP_FORMAT_STR, name="pil2webp"),
        ),
    )

    # https://developers.google.com/speed/webp/docs/cwebp
    _CWEBP_BASE_ARGS: tuple[str, ...] = (
        "-mt",
        "-q",
        "100",
        "-m",
        "6",
        "-o",
        "-",
        "-quiet",
        # https://groups.google.com/a/webmproject.org/g/webp-discuss/c/0GmxDmlexek
        "-lossless",
        "-sharp_yuv",
        "-alpha_filter",
        "best",
    )
    _NEAR_LOSSLESS_ARGS: tuple[str, ...] = ("-near_lossless", "0")

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Widen acceptable inputs if cwebp is modern enough for PPM/TIFF."""
        super().__init__(*args, **kwargs)
        if CWebPTool.IS_MODERN_CWEBP:
            self._input_file_formats = self._input_file_formats | MODERN_CWEBP_FORMATS

    def cwebp_args(self) -> tuple[str, ...]:
        """Build the runtime cwebp argument tuple (no exec / input path)."""
        meta = ("all",) if self.config.keep_metadata else ("none",)
        args: tuple[str, ...] = (*self._CWEBP_BASE_ARGS, "-metadata", *meta)
        if self.config.near_lossless:
            args = (*args, *self._NEAR_LOSSLESS_ARGS)
        return args


# ---------------------------------------------------------------------------
# Animated GIF → animated WebP (image handler, not container)
# ---------------------------------------------------------------------------


class Gif2WebPAnimatedLossless(ImageHandler):
    """
    Convert animated GIF to animated WebP via gif2webp.

    This is intentionally an :class:`ImageHandler` rather than a container:
    gif2webp takes the entire input GIF as a single argument and writes a
    single WebP. There are no frames to walk on the picopt side.
    """

    OUTPUT_FORMAT_STR = _WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(_WEBP_FORMAT_STR, lossless=True, animated=True)
    INPUT_FILE_FORMATS = frozenset({GifAnimated.OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".webp",)

    PIPELINE: tuple[tuple[Tool, ...], ...] = ((Gif2WebPTool(),),)

    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"quality": 100, "method": 6, "lossless": True}
    )

    # https://developers.google.com/speed/webp/docs/gif2webp
    _GIF2WEBP_BASE_ARGS: tuple[str, ...] = (
        "-mt",
        "-q",
        "100",
        "-m",
        "6",
        "-o",
        "-",
        "-quiet",
        "-min_size",
    )

    def gif2webp_args(self) -> tuple[str, ...]:
        """Args for extrnal program."""
        meta = ("all",) if self.config.keep_metadata else ("none",)
        return (*self._GIF2WEBP_BASE_ARGS, "-metadata", *meta)


# ---------------------------------------------------------------------------
# Animated WebP — container handlers
# ---------------------------------------------------------------------------

# Common PIL save options shared by every animated-WebP handler.
_ANIMATED_WEBP_PIL_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {"quality": 100, "method": 6, "lossless": True, "minimize_size": True}
)

# Frame-extraction PIL options when frames need to be written as
# intermediate WebP files (img2webp / PIL fallback).
_ANIMATED_WEBP_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {
        "format": _WEBP_FORMAT_STR,
        "method": 0,
        "lossless": True,
        "quality": 0,
    }
)


class WebPAnimatedLossless(ImageAnimated, ABC):
    """Common WebPAnimated Tool methods."""

    OUTPUT_FORMAT_STR = _WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(_WEBP_FORMAT_STR, lossless=True, animated=True)
    SUFFIXES: tuple[str, ...] = (".webp",)
    PIL2_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_PIL_KWARGS
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_FRAME_KWARGS

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize instance."""
        super().__init__(*args, **kwargs)
        self._working_tmp_dir: Path | None = None
        self._frame_index_width: int = 0

    # ----- frame file plumbing
    def _ensure_tmp_dir(self) -> Path:
        if self._working_tmp_dir is None:
            self._working_tmp_dir = Path(mkdtemp(suffix=_hash_tmp_dir_suffix(self)))
        return self._working_tmp_dir

    def _frame_path(self, index: int) -> Path:
        n = str(index).zfill(self._frame_index_width)
        return self._ensure_tmp_dir() / f"frame_{n}.webp"

    # ----- pack
    #
    def _cleanup_tmp_dir(self) -> None:
        if self._working_tmp_dir is not None:
            shutil.rmtree(self._working_tmp_dir, ignore_errors=True)
            self._working_tmp_dir = None


class Img2WebPAnimatedLossless(WebPAnimatedLossless):
    """
    Animated WebP packed via ``img2webp``.

    During :meth:`walk` (inherited), Pillow's frame iterator yields frames
    one by one and our overridden :meth:`_unpack_frame` saves each one as
    a lossless WebP file inside a per-handler tmp directory. At pack time,
    :class:`Img2WebPTool` shells out with one ``-frame`` argument per
    saved file. The tmp dir is removed in a ``finally`` from
    :meth:`pack_into` regardless of success.
    """

    INPUT_FILE_FORMATS = frozenset(
        {WebPAnimatedLossless.OUTPUT_FILE_FORMAT, *PngAnimated.INPUT_FILE_FORMATS}
    )

    PIPELINE: tuple[tuple[Tool, ...], ...] = ((Img2WebPTool(),),)

    # https://developers.google.com/speed/webp/docs/img2webp
    _IMG2WEBP_BASE_ARGS: tuple[str, ...] = (
        "-min_size",
        "-q",
        "100",
        "-m",
        "6",
        "-o",
        "-",
        "-sharp_yuv",
    )
    _LOSSLESS_OPTS: tuple[str, ...] = ("-lossless",)
    _NEAR_LOSSLESS_OPTS: tuple[str, ...] = ("-near_lossless", "0")

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Init instance variables."""
        super().__init__(*args, **kwargs)
        if CWebPTool.IS_MODERN_CWEBP:
            self._input_file_formats = self._input_file_formats | MODERN_CWEBP_FORMATS
        self._frame_paths: list[Path] = []

    # ----- walk overrides

    @override
    def _unpack_frame(
        self,
        frame,
        frame_index: int,
        frame_info: dict,
    ) -> PathInfo:
        self.populate_frame_info(frame, frame_info)
        path = self._frame_path(frame_index)
        frame.save(path, **self.PIL2_FRAME_KWARGS)
        self._frame_paths.append(path)
        return PathInfo(
            path_info=self.path_info,
            frame=frame_index,
            container_parents=self.path_info.container_path_history(),
            noop=True,
        )

    @override
    def walk(self) -> Generator[PathInfo]:
        # img2webp owns the entire packing strategy; we always repack.
        self._frame_index_width = len(str(self.info.get("n_frames", 1)))
        self._ensure_tmp_dir()
        yield from super().walk()
        self._do_repack = True

    # ----- pack

    @override
    def pack_into(self) -> BinaryIO:
        try:
            return self.first_stage().run_pack(self)
        finally:
            self._cleanup_tmp_dir()

    def img2webp_args(self) -> tuple[str, ...]:
        """Args for external program."""
        runtime: tuple[str, ...] = (
            self._NEAR_LOSSLESS_OPTS
            if self.config.near_lossless
            else self._LOSSLESS_OPTS
        )
        if loop := self.frame_info.get("loop"):
            runtime = (*runtime, "-loop", str(loop))

        out: list[str] = [*self._IMG2WEBP_BASE_ARGS, *runtime]
        durations = self.frame_info.get("duration", ())
        for frame_duration, frame_path in zip_longest(
            durations, sorted(self._frame_paths), fillvalue=None
        ):
            if frame_path is None:
                continue
            if frame_duration is not None:
                out += ["-d", str(frame_duration)]
            out.append(str(frame_path))
        return tuple(out)


class WebPMuxAnimatedLossless(WebPAnimatedLossless):
    """
    Animated WebP unpacked and repacked via ``webpmux``.

    Only meaningful when the input is already animated WebP — webpmux
    can't read anything else. Both unpack and pack go through the same
    binary; we override :meth:`walk` entirely (replacing Pillow's frame
    iterator) and :meth:`pack_into` calls :class:`WebPMuxTool`.
    """

    INPUT_FILE_FORMATS = frozenset({WebPAnimatedLossless.OUTPUT_FILE_FORMAT})

    PIPELINE: tuple[tuple[Tool, ...], ...] = ((WebPMuxTool(),),)

    _DURATION_RE: re.Pattern[str] = re.compile(r"frame \d+: (\d+) ms")
    _DEFAULT_DURATION_MS: int = 100

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize instance."""
        super().__init__(*args, **kwargs)
        self._durations: dict[int, int] = {}

    # ----- frame file plumbing
    def _webpmux_exec(self) -> tuple[str, ...]:
        """Resolve ``webpmux`` argv prefix from the probed tool instance."""
        return self.resolved_tool(WebPMuxTool).exec_args()

    def _read_durations(self, num_frames: int) -> dict[int, int]:
        cmd = (*self._webpmux_exec(), "-info", str(self.original_path))
        result = subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        text = result.stdout.decode("utf-8", errors="replace")
        durations = self._DURATION_RE.findall(text)
        if durations:
            return {i: int(d) for i, d in enumerate(durations, start=1)}
        return dict.fromkeys(range(1, num_frames + 1), self._DEFAULT_DURATION_MS)

    # ----- walk

    @override
    def walk(self) -> Generator[PathInfo]:
        self._printer.container_unpacking(self.path_info)
        n_frames = self.info["n_frames"]
        self._frame_index_width = len(str(n_frames))
        self._ensure_tmp_dir()

        webpmux = self._webpmux_exec()
        container_parents = self.path_info.container_path_history()
        extracted: list[Path] = []
        for frame_index in range(1, n_frames + 1):
            frame_path = self._frame_path(frame_index)
            cmd = (
                *webpmux,
                "-get",
                "frame",
                str(frame_index),
                str(self.original_path),
                "-o",
                str(frame_path),
            )
            try:
                subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
            except subprocess.CalledProcessError:
                break
            yield PathInfo(
                path_info=self.path_info,
                path=frame_path,
                frame=frame_index,
                container_parents=container_parents,
            )
            if frame_path.exists():
                extracted.append(frame_path)

        if not extracted:
            msg = "No frames found — is this actually an animated WebP?"
            raise ValueError(msg)

        self._durations = self.info.get("durations") or self._read_durations(
            len(extracted)
        )
        self._do_repack = True
        self._walk_finish()

    # ----- pack

    @override
    def pack_into(self) -> BinaryIO:
        try:
            return self.first_stage().run_pack(self)
        finally:
            self._cleanup_tmp_dir()

    def webpmux_pack_args(self) -> tuple[str, ...]:
        """Args for external tool."""
        out: list[str] = []
        for index, dur in self._durations.items():
            out.extend(["-frame", str(self._frame_path(index)), f"+{dur}"])
        out.extend(["-loop", "0", "-o", "-"])
        return tuple(out)


class PILPackWebPAnimatedLossless(ImageAnimated):
    """
    Pure-Pillow animated WebP fallback.

    The inherited :meth:`ImageAnimated.walk` extracts frames in memory and
    the inherited :meth:`ImageAnimated.pack_into` calls
    ``Image.save(save_all=True)`` with this class's PIL kwargs. Pillow is
    a hard picopt dependency, so this handler is always available.

    PIPELINE contains a single :class:`PILSaveTool` sentinel so the doctor
    command lists this handler with a real tool entry instead of a blank
    "no stages" line. The sentinel is informational only —
    :meth:`ContainerHandler.optimize` calls :meth:`pack_into` directly and
    never iterates the pipeline as stages.
    """

    OUTPUT_FORMAT_STR = _WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(_WEBP_FORMAT_STR, lossless=True, animated=True)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, *PngAnimated.INPUT_FILE_FORMATS}
    )
    SUFFIXES: tuple[str, ...] = (".webp",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (PILSaveTool(target_format_str=_WEBP_FORMAT_STR, name="pil2webp"),),
    )

    PIL2_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_PIL_KWARGS
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_FRAME_KWARGS


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

# Convert-target preference for animated-WebP outputs from non-WebP
# inputs (animated GIF, animated PNG). webpmux is intentionally absent —
# it can only read existing animated WebP. img2webp is preferred for
# size; PIL is the always-available fallback.
_ANIMATED_CONVERT_FROM_OTHER: tuple[type[Handler], ...] = (
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
)


PLUGIN = Plugin(
    name="WEBP",
    handlers=(
        WebPLossless,
        Gif2WebPAnimatedLossless,
        Img2WebPAnimatedLossless,
        WebPMuxAnimatedLossless,
        PILPackWebPAnimatedLossless,
    ),
    routes=(
        # Still WebP → still WebPLossless.
        Route(
            file_format=WebPLossless.OUTPUT_FILE_FORMAT,
            native=WebPLossless,
        ),
        Route(
            file_format=Png.OUTPUT_FILE_FORMAT,
            convert=(WebPLossless,),
        ),
        Route(
            file_format=Gif.OUTPUT_FILE_FORMAT,
            convert=(WebPLossless,),
        ),
        # Animated WebP input: webpmux is the natural native handler
        # because it can round-trip without re-encoding via Pillow.
        # Img2Webp / PILPack are listed as convert alternatives so the
        # routing layer can fall back if webpmux is missing.
        Route(
            file_format=WebPMuxAnimatedLossless.OUTPUT_FILE_FORMAT,
            native=WebPMuxAnimatedLossless,
            convert=_ANIMATED_CONVERT_FROM_OTHER,
        ),
        # Convert from animated GIF: prefer gif2webp (purpose-built);
        # fall back to img2webp / PIL via PNG-frame extraction.
        Route(
            file_format=GifAnimated.OUTPUT_FILE_FORMAT,
            convert=(
                Gif2WebPAnimatedLossless,
                *_ANIMATED_CONVERT_FROM_OTHER,
            ),
        ),
        # Convert from animated PNG: img2webp / PIL
        # doesn't read PNG.
        Route(
            file_format=PngAnimated.OUTPUT_FILE_FORMAT,
            convert=_ANIMATED_CONVERT_FROM_OTHER,
        ),
    ),
    convert_targets=(
        WebPLossless,
        Img2WebPAnimatedLossless,
        PILPackWebPAnimatedLossless,
    ),
    default_enabled=True,
)
