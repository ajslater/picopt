"""Animated WebP Image Handler."""

from abc import ABC
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO

from confuse import AttrDict
from PIL.WebPImagePlugin import WebPImageFile
from typing_extensions import override

from picopt.formats import MODERN_CWEBP_FORMATS, FileFormat
from picopt.handlers.container.animated import ImageAnimated
from picopt.handlers.image.png import PngAnimated
from picopt.handlers.image.webp import WebPBase
from picopt.path import PathInfo


class Img2WebPAnimatedBase(ImageAnimated, ABC):
    """Animated WebP container."""

    OUTPUT_FORMAT_STR: str = WebPBase.OUTPUT_FORMAT_STR
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"format": WebPImageFile.format, "method": 0}
    )
    PROGRAMS = (("img2webp", "pil2native"),)
    # https://developers.google.com/speed/webp/docs/img2webp
    IMG2WEBP_ARGS_PREFIX: tuple[str, ...] = (
        "-min_size",
        "-q",
        "100",
        "-m",
        "6",
        # advanced
        "-sharp_yuv",
    )
    WORKING_ID: str = PROGRAMS[0][0]

    def __init__(self, config: AttrDict, *args, **kwargs):
        """Initialize extra input formats."""
        super().__init__(config, *args, **kwargs)
        if config.computed.is_modern_cwebp:
            self._input_file_formats |= MODERN_CWEBP_FORMATS
        self._frame_paths = []

    @override
    def _unpack_frame(self, frame, frame_index: int, frame_info: dict) -> PathInfo:
        self.populate_frame_info(frame, frame_info)
        working_path = self.get_working_path(".img2webp-input")
        path_info = PathInfo(
            path_info=self.path_info,
            frame=frame_index,
            container_parents=self.path_info.container_path_history(),
            noop=True,
        )
        frame_path = Path(str(working_path) + "." + path_info.name())
        frame.save(frame_path, **self.PIL2_FRAME_KWARGS)
        self._frame_paths.append(frame_path)
        return path_info

    @override
    def _walk_finish(self):
        self._do_repack = True
        if not self.config.verbose:
            return
        self._printer.done()

    @override
    def optimize(self) -> BinaryIO:
        """Run pack_into."""
        self._printer.img2webp_repacking(self.path_info)
        buffer = self.pack_into()
        self._printer.container_repacking_done()
        return buffer

    def _get_output_path(self):
        output_path = self.get_working_path(f".{self.WORKING_ID}-output")
        output_path_tmp = bool(self.path_info.path)
        return output_path, output_path_tmp

    def img2webp(self, opts: tuple[str, ...]) -> BinaryIO:
        """Optimize using img2webp."""
        args = ["img2webp"]
        args.extend(self.IMG2WEBP_ARGS_PREFIX)
        if opts:
            args.extend(opts)
        input_path = self.path_info.path
        input_path_tmp = False
        output_path, output_path_tmp = self._get_output_path()

        args.extend(["-o", str(output_path)])

        duration = self.frame_info.get("duration", [])

        frame_args = []
        for frame_duration, frame_path in zip_longest(
            duration, sorted(self._frame_paths), fillvalue=None
        ):
            if not frame_path:
                continue
            if frame_duration is not None:
                frame_args.extend(["-d", str(frame_duration)])
            frame_args.append(str(frame_path))

        args.extend(frame_args)

        input_buffer = BytesIO()
        return self.run_ext_fs(
            tuple(args),
            input_buffer,
            input_path,
            output_path,
            input_path_tmp=input_path_tmp,
            output_path_tmp=output_path_tmp,
        )

    def _get_opts(self) -> tuple[str, ...]:
        return ()

    @override
    def pack_into(self) -> BinaryIO:
        opts = self._get_opts()
        return self.img2webp(opts)


class Img2WebPAnimatedLossless(Img2WebPAnimatedBase):
    """Animated Lossless WebP Handler."""

    OUTPUT_FILE_FORMAT: FileFormat = FileFormat(
        Img2WebPAnimatedBase.OUTPUT_FORMAT_STR, lossless=True, animated=True
    )
    INPUT_FILE_FORMATS: frozenset[FileFormat] = frozenset(
        {*PngAnimated.INPUT_FILE_FORMATS, OUTPUT_FILE_FORMAT}
    )
    PROGRAMS = (("pil2png",), ("img2webp", "pil2native"))
    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {**Img2WebPAnimatedBase.PIL2_FRAME_KWARGS, "lossless": True, "quality": 0}
    )
    IMG2WEBP_ARGS_PREFIX = (*Img2WebPAnimatedBase.IMG2WEBP_ARGS_PREFIX,)
    _LOSSLESS_OPTS: tuple[str, ...] = ("-lossless",)
    _NEAR_LOSSLESS_OPTS: tuple[str, ...] = ("-near_lossless", "0")

    @override
    def _get_opts(self) -> tuple[str, ...]:
        """Optimize using img2webp and with runtime optional arguments."""
        opts = (
            self._NEAR_LOSSLESS_OPTS
            if self.config.near_lossless
            else self._LOSSLESS_OPTS
        )
        if loop := self.frame_info.get("loop"):
            opts += ("-loop", str(loop))
        return tuple(opts)
