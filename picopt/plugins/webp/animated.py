"""Animated WebP handlers: gif2webp, img2webp, webpmux, and PIL fallback."""

from __future__ import annotations

import re
import shutil
import subprocess
from abc import ABC
from itertools import zip_longest
from pathlib import Path
from tempfile import mkdtemp
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, BinaryIO

from loguru import logger
from typing_extensions import override

from picopt.path import PathInfo
from picopt.plugins.base import ImageAnimated, ImageHandler, PILSaveTool, Tool
from picopt.plugins.base.format import FileFormat
from picopt.plugins.gif import GifAnimated
from picopt.plugins.png import PngAnimated
from picopt.plugins.webp.const import MODERN_CWEBP_FORMATS, WEBP_FORMAT_STR
from picopt.plugins.webp.tools import (
    CWEBP_TOOL,
    Gif2WebPTool,
    Img2WebPTool,
    WebPMuxTool,
    hash_tmp_dir_suffix,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class Gif2WebPAnimatedLossless(ImageHandler):
    """
    Convert animated GIF to animated WebP via gif2webp.

    This is intentionally an :class:`ImageHandler` rather than a container:
    gif2webp takes the entire input GIF as a single argument and writes a
    single WebP. There are no frames to walk on the picopt side.
    """

    OUTPUT_FORMAT_STR = WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WEBP_FORMAT_STR, lossless=True, animated=True)
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


# Common PIL save options shared by every animated-WebP handler.
_ANIMATED_WEBP_PIL_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {"quality": 100, "method": 6, "lossless": True, "minimize_size": True}
)

# Frame-extraction PIL options when frames need to be written as
# intermediate WebP files (img2webp / PIL fallback).
_ANIMATED_WEBP_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
    {
        "format": WEBP_FORMAT_STR,
        "method": 0,
        "lossless": True,
        "quality": 0,
    }
)


class WebPAnimatedLossless(ImageAnimated, ABC):
    """Common WebPAnimated Tool methods."""

    OUTPUT_FORMAT_STR = WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WEBP_FORMAT_STR, lossless=True, animated=True)
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
            self._working_tmp_dir = Path(mkdtemp(suffix=hash_tmp_dir_suffix(self)))
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

    @override
    def get_staging_dir(self) -> Path | None:
        """Expose the frame tmp dir so the scheduler can clean it on rollback."""
        return self._working_tmp_dir


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
        if CWEBP_TOOL.is_modern:
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
                # img2webp rejects durations <= 0 ("Invalid negative
                # duration"). Some sources (e.g. scraped animated WebPs)
                # carry 0ms frame durations, so clamp to its 1ms minimum.
                out += ["-d", str(max(1, int(frame_duration)))]
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
        if self.config.verbose > 1:
            logger.info(f"Unpacking {self.path_info.full_output_name()}…")
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

        self._durations = self._read_durations(len(extracted))
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

    OUTPUT_FORMAT_STR = WEBP_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(WEBP_FORMAT_STR, lossless=True, animated=True)
    INPUT_FILE_FORMATS = frozenset(
        {OUTPUT_FILE_FORMAT, *PngAnimated.INPUT_FILE_FORMATS}
    )
    SUFFIXES: tuple[str, ...] = (".webp",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (PILSaveTool(target_format_str=WEBP_FORMAT_STR, name="pil2webp"),),
    )

    PIL2_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_PIL_KWARGS
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = _ANIMATED_WEBP_FRAME_KWARGS
