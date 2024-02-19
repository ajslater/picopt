"""Animated images are treated like containers."""
from abc import ABC
from collections.abc import Generator
from io import BytesIO
from types import MappingProxyType
from typing import Any

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngImageFile
from termcolor import cprint

from picopt.formats import FileFormat
from picopt.handlers.container import ContainerHandler
from picopt.path import PathInfo

ANIMATED_INFO_KEYS = ("bbox", "blend", "disposal", "duration")


class ImageAnimated(ContainerHandler, ABC):
    """Animated image container."""

    PROGRAMS = (("pil2native",),)
    PIL2_FRAME_KWARGS = MappingProxyType(
        {"format": PngImageFile.format, "compress_level": 0}
    )
    PIL2_KWARGS: MappingProxyType[str, Any] = MappingProxyType({})

    @classmethod
    def identify_format(cls, path_info: PathInfo) -> FileFormat | None:  # noqa: ARG003
        """Return the format if this handler can handle this path."""
        return cls.OUTPUT_FILE_FORMAT

    def unpack_into(self) -> Generator[PathInfo, None, None]:
        """Unpack webp into temp dir."""
        frame_index = 1
        frame_info = {}
        with Image.open(self.original_path) as image:
            for frame in ImageSequence.Iterator(image):
                # Save the frame as quickly as possible with the correct
                #   lossless format. Real optimization happens later with
                #   the specific handler.
                # XXX It would be better to do what i do for mpo and read
                #   the bytes directly because this shows bad numbers for
                #   compressing uncompressed frames. But Pillow doesn't have
                #   raw access to frames.
                with BytesIO() as frame_buffer:
                    frame.save(
                        frame_buffer,
                        **self.PIL2_FRAME_KWARGS,
                    )
                    for key in ANIMATED_INFO_KEYS:
                        value = frame.info.get(key)
                        if value is not None:
                            if key not in frame_info:
                                frame_info[key] = []
                            frame_info[key].append(value)
                    frame_buffer.seek(0)
                    frame_path_info = PathInfo(
                        self.path_info.top_path,
                        self.path_info.mtime(),
                        self.path_info.convert,
                        self.path_info.is_case_sensitive,
                        frame=frame_index,
                        data=frame_buffer.read(),
                        container_paths=self.get_container_paths(),
                    )
                if self.config.verbose:
                    cprint(".", end="")
                yield frame_path_info
                frame_index += 1
        image.close()
        for key in tuple(frame_info):
            value = frame_info[key]
            if value is not None:
                frame_info[key] = tuple(value)
        self.frame_info = frame_info

    def pack_into(self) -> BytesIO:
        """Remux the optimized frames into an animated webp."""
        sorted_pairs = sorted(
            self._optimized_contents.items(),
            key=lambda pair: 0 if pair[0].frame is None else pair[0].frame,
        )
        head_image_data = sorted_pairs.pop()[1]

        # Collect frames as images.
        total_len = 0
        append_images = []
        while sorted_pairs:
            _, frame_data = sorted_pairs.pop()
            total_len += len(frame_data)
            frame = Image.open(BytesIO(frame_data))
            append_images.append(frame)
            if self.config.verbose:
                cprint(".", end="")

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
