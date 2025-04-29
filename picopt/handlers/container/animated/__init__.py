"""Animated images are treated like containers."""

from abc import ABC
from collections.abc import Generator, Mapping
from io import BytesIO
from types import MappingProxyType
from typing import Any

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngImageFile

from picopt.formats import FileFormat
from picopt.handlers.container import PackingContainerHandler
from picopt.handlers.metadata import PrepareInfoMixin
from picopt.path import PathInfo

ANIMATED_INFO_KEYS = ("bbox", "blend", "disposal", "duration")


class ImageAnimated(PrepareInfoMixin, PackingContainerHandler, ABC):
    """Animated image container."""

    PROGRAMS = (("pil2native",),)
    PIL2_FRAME_KWARGS = MappingProxyType(
        {"format": str(PngImageFile.format), "compress_level": 0}
    )
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})
    CONTAINER_TYPE = "Animated Image"

    def __init__(self, *args, info: Mapping[str, Any], **kwargs):
        """Set image metadata."""
        super().__init__(*args, **kwargs)
        self.set_info(info)

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:  # noqa: ARG003
        """Return the format if this handler can handle this path."""
        return cls.OUTPUT_FILE_FORMAT

    def _unpack_frame(self, frame, frame_index: int, frame_info: dict) -> PathInfo:
        """
        Save the frame as quickly as possible with the correct lossless format.

        Real optimization happens later with the specific handler.
        It would be better to do what i do for mpo and read the bytes directly
        because this shows bad numbers for compressing uncompressed frames. But
        Pillow doesn't have raw access to frames.
        """
        with BytesIO() as frame_buffer:
            frame.save(
                frame_buffer,
                **self.PIL2_FRAME_KWARGS,  # type: ignore[reportArgumentType]
            )
            for key in ANIMATED_INFO_KEYS:
                value = frame.info.get(key)
                if value is not None:
                    if key not in frame_info:
                        frame_info[key] = []
                    frame_info[key].append(value)
            frame_buffer.seek(0)
            return PathInfo(
                path_info=self.path_info,
                frame=frame_index,
                data=frame_buffer.read(),
                container_parents=self.path_info.container_path_history(),
            )

    def _save_frame_info(self, frame_info: dict):
        for key in tuple(frame_info):
            value = frame_info[key]
            if value is not None:
                frame_info[key] = tuple(value)
        self.frame_info = frame_info

    def walk(self) -> Generator[PathInfo]:
        """Unpack animated image frames with PIL."""
        self._printer.container_unpacking(self.path_info)
        frame_info = {}
        with Image.open(self.original_path) as image:
            for index, frame in enumerate(ImageSequence.Iterator(image), start=1):
                frame_path_info = self._unpack_frame(frame, index, frame_info)
                yield frame_path_info
        # Animated images need a double close because of some PIL bug.
        image.close()
        self._save_frame_info(frame_info)
        self._walk_finish()

    def pack_into(self) -> BytesIO:
        """Remux the optimized frames into an animated webp."""
        sorted_frames = sorted(
            self._optimized_contents,
            key=lambda p: 0 if p.frame is None else p.frame,
        )
        # clear optimized contents
        self.optimized_contents = set()

        head_image_data = sorted_frames.pop().data()

        # Collect frames as images.
        append_images = []
        while sorted_frames:
            frame_data = sorted_frames.pop().data()
            frame = Image.open(BytesIO(frame_data))
            append_images.append(frame)
            self._printer.packed_message()

        # Prepare info
        info = dict(self.prepare_info(self.OUTPUT_FORMAT_STR))
        info.update(self.frame_info)

        # Save Frames
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
