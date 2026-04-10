"""
Animated image container handler base.

An animated image is a container of frames. Optimization rebuilds the
container from optimized frames using the appropriate packing tool.
"""

from __future__ import annotations

from abc import ABC
from io import BytesIO
from statistics import mean
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, BinaryIO

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngImageFile
from typing_extensions import override

from picopt.path import PathInfo
from picopt.plugins.base.container import ContainerHandler
from picopt.plugins.base.image import ImageHandler

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from picopt.formats import FileFormat

ANIMATED_INFO_KEYS = ("bbox", "blend", "disposal", "duration")


class ImageAnimated(ImageHandler, ContainerHandler, ABC):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """
    Animated image container.

    Inherits ``prepare_info`` from :class:`ImageHandler` and walking/packing
    semantics from :class:`ContainerHandler`. The optimize() method comes
    from ContainerHandler (calls pack_into).

    This has diamond inheritance but I think it's done safely.
    """

    PIL2_FRAME_KWARGS: MappingProxyType[str, Any] = MappingProxyType(
        {"format": str(PngImageFile.format), "compress_level": 0}
    )
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})
    CONTAINER_TYPE: str = "Animated Image"

    def __init__(self, *args, info: Mapping[str, Any], **kwargs) -> None:
        """Init frame info."""
        super().__init__(*args, info=info, **kwargs)
        self.frame_info: dict[str, Any] = {}

    @override
    @classmethod
    def identify_format(cls, path_info) -> FileFormat | None:
        """Animated handlers identify by suffix; the PIL detector picks them up based on the n_frames check during PIL inspection."""
        return cls.OUTPUT_FILE_FORMAT

    # ----------------------------------------------------------- unpacking

    @staticmethod
    def populate_frame_info(frame, frame_info: dict) -> None:
        """Populate frame_info."""
        for key in ANIMATED_INFO_KEYS:
            value = frame.info.get(key)
            if value is not None:
                if key not in frame_info:
                    frame_info[key] = []
                frame_info[key].append(value)

    def _unpack_frame(self, frame, frame_index: int, frame_info: dict) -> PathInfo:
        """Save the frame as quickly as possible to a lossless intermediate."""
        self.populate_frame_info(frame, frame_info)
        with BytesIO() as frame_buffer:
            frame.save(frame_buffer, **self.PIL2_FRAME_KWARGS)
            frame_buffer.seek(0)
            return PathInfo(
                path_info=self.path_info,
                frame=frame_index,
                data=frame_buffer.read(),
                container_parents=self.path_info.container_path_history(),
            )

    @staticmethod
    def _fix_duration(frame_info: dict, index: int) -> None:
        duration = frame_info.get("duration")
        if duration is None:
            return
        num_missing = index - len(duration)
        if num_missing > 0:
            mean_duration = mean(duration)
            duration.extend([mean_duration] * num_missing)

    def _save_frame_info(self, frame_info: dict[str, Any]) -> None:
        for key in tuple(frame_info):
            value = frame_info[key]
            if value is not None:
                frame_info[key] = tuple(value)
        self.frame_info = frame_info

    @override
    def walk(self) -> Generator[PathInfo]:
        """Yield each frame as a child PathInfo."""
        self._printer.container_unpacking(self.path_info)
        frame_info: dict[str, Any] = {}
        index = 0
        with Image.open(self.original_path) as image:
            for index, frame in enumerate(ImageSequence.Iterator(image), start=1):
                yield self._unpack_frame(frame, index, frame_info)
        image.close()  # animated images need a double close
        self._fix_duration(frame_info, index)
        self._save_frame_info(frame_info)
        self._walk_finish()

    @override
    def optimize(self) -> BinaryIO:
        """
        Containers always pack; defer to ContainerHandler.optimize.

        Without this explicit override the MRO would resolve ``optimize`` to
        :class:`ImageHandler.optimize`, which iterates pipeline stages and
        never calls :meth:`pack_into`. Animated images must always go
        through ``pack_into`` because their PIPELINE describes the *packing*
        tool (img2webp, webpmux, …), not per-buffer transformations.
        """
        return ContainerHandler.optimize(self)

    # ------------------------------------------------------------ packing

    @override
    def pack_into(self) -> BinaryIO:
        """
        Default packer: re-encode the frames through PIL.

        Subclasses with format-specific packers (img2webp, webpmux) override.
        """
        sorted_frames = sorted(
            self._optimized_contents,
            key=lambda p: 0 if p.frame is None else p.frame,
        )
        self._optimized_contents = set()
        if not sorted_frames:
            msg = f"{type(self).__name__} has no frames to pack"
            raise ValueError(msg)

        head_image_data = sorted_frames[0].data()
        append_images = []
        for path_info in sorted_frames[1:]:
            frame = Image.open(BytesIO(path_info.data()))
            append_images.append(frame)
            self._printer.packed()

        info = dict(self.prepare_info(self.OUTPUT_FORMAT_STR))
        info.update(self.frame_info)

        output_buffer = BytesIO()
        with Image.open(BytesIO(head_image_data)) as image:
            image.save(
                output_buffer,
                self.OUTPUT_FORMAT_STR,
                save_all=True,
                append_images=append_images,
                **self.PIL2_KWARGS,
                **info,
            )
        return output_buffer
