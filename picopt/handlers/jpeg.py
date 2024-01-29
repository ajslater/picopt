"""JPEG format."""
from io import BytesIO
from pathlib import Path

import piexif
from PIL.JpegImagePlugin import JpegImageFile

from picopt.formats import MPO_FILE_FORMAT, FileFormat
from picopt.handlers.image import ImageHandler

MPO_METADATA: int = 45058
MPO_TYPE_PRIMARY: str = "Baseline MP Primary Image"


class Jpeg(ImageHandler):
    """JPEG format class."""

    OUTPUT_FORMAT_STR = JpegImageFile.format
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, False, False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    PROGRAMS = (("mozjpeg", "jpegtran", "pil2jpeg"),)
    _JPEGTRAN_ARGS_PREFIX = ("-optimize", "-progressive")
    # PIL Cannot save jpegs losslessly

    @classmethod
    def get_default_suffix(cls) -> str:
        """Override default suffix for jpeg."""
        return ".jpg"

    @classmethod
    def get_suffixes(cls, default_suffix: str) -> frozenset:
        """Initialize suffix instance variables."""
        return frozenset((default_suffix, "." + cls.OUTPUT_FORMAT_STR.lower()))

    def _jpegtran(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Run the jpegtran type program."""
        args = [*exec_args, *self._JPEGTRAN_ARGS_PREFIX]
        args += ["-copy"]
        if self.config.keep_metadata:
            args += ["all"]
        else:
            args += ["none"]
        args += ["-outfile", str(new_path), str(old_path)]
        self.run_ext(tuple(args))
        return new_path

    def mozjpeg(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Create argument list for mozjpeg."""
        return self._jpegtran(exec_args, old_path, new_path)

    def jpegtran(
        self, exec_args: tuple[str, ...], old_path: Path, new_path: Path
    ) -> Path:
        """Create argument list for jpegtran."""
        return self._jpegtran(exec_args, old_path, new_path)

    def _mpo2jpeg_get_offsets(self, old_path) -> tuple[int, int]:
        """Get Primary JPEG Offsets."""
        mpo_info = self.info.pop("mpinfo", {})
        mpo_metadata_list = mpo_info.get(MPO_METADATA, ())

        for mpo_metadata in mpo_metadata_list:
            attr = mpo_metadata.get("Attribute", {})
            mp_type = attr.get("MPType")
            if mp_type == MPO_TYPE_PRIMARY:
                offset = mpo_metadata.get("DataOffset")
                size = mpo_metadata.get("Size")
                break
        else:
            offset = size = None

        result = (offset, size)
        if None in result:
            reason = f"{old_path} could not find {MPO_TYPE_PRIMARY} in MPO"
            raise ValueError(reason)
        return result  # type: ignore

    def _mpo2jpeg_copy_exif(self, jpeg_data) -> bytes:
        """Copy MPO EXIF into JPEG."""
        if exif := self.info.get("exif"):
            jpeg_data_with_exif = BytesIO()
            piexif.insert(exif, jpeg_data, jpeg_data_with_exif)
            image = jpeg_data_with_exif.read()
        else:
            image = jpeg_data
        return image

    def pil2jpeg(
        self,
        exec_args: tuple[str, ...],  # noqa: ARG002
        old_path: Path,
        new_path: Path,
    ):
        """Convert MPOs with primary images to jpeg."""
        # XXX Much work because PIL doesn't have direct unprocessed file bytes access.
        if self.input_file_format != MPO_FILE_FORMAT:
            return old_path

        offset, size = self._mpo2jpeg_get_offsets(old_path)

        with old_path.open("rb") as mpo_file:
            mpo_file.seek(offset)
            jpeg_image = mpo_file.read(size)

        jpeg_image = self._mpo2jpeg_copy_exif(jpeg_image)

        with new_path.open("wb") as jpeg_file:
            jpeg_file.write(jpeg_image)

        self.input_file_format = self.OUTPUT_FILE_FORMAT
        return new_path
