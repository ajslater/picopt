"""Animated WebP Image Handler."""

import re
import shutil
import subprocess
from collections.abc import Generator
from io import BytesIO
from subprocess import CalledProcessError
from types import MappingProxyType
from typing import Any, BinaryIO

from PIL.WebPImagePlugin import WebPImageFile
from typing_extensions import override

from picopt.formats import FileFormat
from picopt.handlers.container.animated.webpbase import WebpAnimatedBase
from picopt.handlers.image.png import PngAnimated
from picopt.handlers.image.webp import WebPBase
from picopt.path import PathInfo


class WebPMuxAnimatedBase(WebpAnimatedBase):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {**WebPBase.PIL2_KWARGS, "minimize_size": True}
    )
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"format": WebPImageFile.format, "method": 0}
    )
    PROGRAMS = (("webpmux",),)

    @staticmethod
    def run(cmd: list[str] | tuple[str, ...]):
        """Run a shell command and raise on error."""
        return subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
        )

    def _extract_timing(self, num_frames: int):
        """Extract timing info."""
        cmd = ("webpmux", "-info", str(self.original_path))
        info = self.run(cmd)
        durations: list[str] = re.findall(r"frame \d+: (\d+) ms", str(info.stdout))
        result = {}
        if durations:
            for i, d in enumerate(durations, start=1):
                result[i] = int(d)
        else:
            for i in range(1, num_frames + 1):
                result[i] = 100
        return result

    @override
    def walk(self) -> Generator[PathInfo]:
        """Unpack animated image frames with webpmux."""
        self._printer.container_unpacking(self.path_info)
        self.set_working_dir()
        self.set_frame_index_width()
        frame_index = 1
        extracted_frames: list[str] = []
        container_parents = self.path_info.container_path_history()
        n_frames = self.info["n_frames"]
        for frame_index in range(1, n_frames + 1):
            frame_path = self.get_frame_path(frame_index)
            try:
                cmd = (
                    "webpmux",
                    "-get",
                    "frame",
                    str(frame_index),
                    str(self.original_path),
                    "-o",
                    str(frame_path),
                )
                self.run(cmd)
                yield PathInfo(
                    self.path_info,
                    path=frame_path,
                    frame=frame_index,
                    container_parents=container_parents,
                )
            except CalledProcessError:
                break
            if frame_path.exists():
                extracted_frames.append(str(frame_path))

        if not extracted_frames:
            reason = "No frames found — is this actually an animated WebP?"
            raise ValueError(reason)

        # TOD make a duratino getter method
        durations = self.info.get("durations", {})
        if not durations:
            durations = self._extract_timing(len(extracted_frames))
        self.durations = durations
        self._walk_finish()

    @override
    def pack_into(self) -> BinaryIO:
        try:
            self.optimized_contents = set()

            cmd = ["webpmux"]
            for frame_index, dur in self.durations.items():
                frame_path = str(self.get_frame_path(frame_index))
                cmd += ["-frame", frame_path, f"+{dur}"]
            cmd += ["-loop", "0", "-o", "-"]
            proc = self.run(cmd)
            return BytesIO(proc.stdout)
        finally:
            shutil.rmtree(self.working_tmp_dir, ignore_errors=True)


class WebPMuxAnimatedLossless(WebPMuxAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        WebPMuxAnimatedBase.OUTPUT_FORMAT_STR, lossless=True, animated=True
    )
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset(
        {*PngAnimated.INPUT_FILE_FORMATS, OUTPUT_FILE_FORMAT}
    )
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {**WebPMuxAnimatedBase.PIL2_FRAME_KWARGS, "lossless": True, "quality": 0}
    )
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {**WebPMuxAnimatedBase.PIL2_KWARGS, "lossless": True}
    )
