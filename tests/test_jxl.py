"""Test the JPEG XL format."""

import shutil
from pathlib import Path
from types import MappingProxyType

import piexif
import pillow_jxl
import pytest
from PIL import Image

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, assert_size_close, get_test_dir
from tests.base import BaseTest

__all__ = ()

# orig, no convert, convert to jxl
FNS = MappingProxyType(
    {
        # A lossless (non XYB) JXL: re-encoded in place.
        "test_jxl_lossless.jxl": (92889, 91811, ("jxl", 91811)),
        # A lossy (XYB encoded) JXL: never touched, exactly like lossy WebP.
        "test_jxl_lossy.jxl": (77911, 77911, ("jxl", 77911)),
        # Lossless still sources convert.
        "test_png.png": (7967, 4152, ("jxl", 3927)),
        "test_gif.gif": (138952, 138944, ("jxl", 115204)),
        # A JPEG must NOT convert without the extra opt-in.
        "test_jpg.jpg": (97373, 87913, ("jpg", 87913)),
    }
)

JPEG_SRC = "test_jpg.jpg"
JPEG_JXL_SIZE = 78762


@pytest.mark.parametrize("fn", FNS)
class TestJxl(BaseTest):
    """Test the JXL handlers over the shared image fixtures."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = FNS

    def test_no_convert(self: "TestJxl", fn: str) -> None:
        """Lossless JXL is optimized in place; lossy JXL is left alone."""
        args = (PROGRAM_NAME, "-rvv", str(self.TMP_ROOT))
        cli.main(args)
        path = self.TMP_ROOT / fn
        assert_size_close(path.stat().st_size, FNS[fn][1])

    def test_convert_to_jxl(self: "TestJxl", fn: str) -> None:
        """Lossless stills convert; JPEG does not without its own flag."""
        args = (PROGRAM_NAME, "-rvv", "-c", "JXL", str(self.TMP_ROOT))
        cli.main(args)
        suffix, size = FNS[fn][2]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert_size_close(path.stat().st_size, size)


@pytest.mark.parametrize("fn", [JPEG_SRC])
class TestJxlFromJpeg(BaseTest):
    """Test the opt-in, reversible JPEG to JXL transcode."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = FNS

    @staticmethod
    def _reconstruct(path: Path) -> tuple[bool, bytes]:
        """Return (carries reconstruction data, the restored JPEG bytes)."""
        result = pillow_jxl.Decoder()(path.read_bytes())
        return bool(result[0]), bytes(result[2])

    def test_convert_jpeg_to_jxl_is_reversible(
        self: "TestJxlFromJpeg", fn: str
    ) -> None:
        """The whole point: the original JPEG must come back byte for byte."""
        original = (self.SOURCE_DIR / fn).read_bytes()
        args = (
            PROGRAM_NAME,
            "-rvv",
            "-c",
            "JXL",
            "--convert-jpeg-to-jxl",
            str(self.TMP_ROOT),
        )
        cli.main(args)

        path = (self.TMP_ROOT / fn).with_suffix(".jxl")
        assert path.exists()
        assert not (self.TMP_ROOT / fn).exists()
        assert_size_close(path.stat().st_size, JPEG_JXL_SIZE)

        has_reconstruction, restored = self._reconstruct(path)
        assert has_reconstruction, "encoded without JPEG reconstruction data"
        assert restored == original, "JPEG did not survive the transcode intact"

    def test_reconstruction_jxl_is_never_reencoded(
        self: "TestJxlFromJpeg", fn: str
    ) -> None:
        """A second pass must not strip the reconstruction data."""
        args = (
            PROGRAM_NAME,
            "-rvv",
            "-c",
            "JXL",
            "--convert-jpeg-to-jxl",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        path = (self.TMP_ROOT / fn).with_suffix(".jxl")
        first = path.read_bytes()

        cli.main((PROGRAM_NAME, "-rvv", str(self.TMP_ROOT)))

        assert path.read_bytes() == first
        has_reconstruction, _ = self._reconstruct(path)
        assert has_reconstruction


EXTRA_FNS = MappingProxyType(
    {
        "test_bmp.bmp": (141430, 141430, ("jxl", 40804)),
        "test_pnm.pnm": (27661, 27661, ("jxl", 11840)),
        "eight.tif": (59640, 59640, ("jxl", 21781)),
    }
)


@pytest.mark.parametrize("fn", EXTRA_FNS)
class TestJxlFromExtraFormats(BaseTest):
    """The pil_convertible sources reach JXL through their convert chain."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = EXTRA_FNS

    def test_convert_to_jxl(self: "TestJxlFromExtraFormats", fn: str) -> None:
        """Convert BMP, PPM and TIFF to JXL."""
        args = (
            PROGRAM_NAME,
            "-rvvx",
            "BMP,PPM,TIFF",
            "-c",
            "JXL",
            str(self.TMP_ROOT),
        )
        cli.main(args)
        suffix, size = EXTRA_FNS[fn][2]
        path = (self.TMP_ROOT / fn).with_suffix("." + suffix)
        assert_size_close(path.stat().st_size, size)


class TestJxlMetadata:
    """--strip-metadata must reach the JXL encoder."""

    TMP_ROOT: Path = get_test_dir() / "metadata"

    @classmethod
    def _write_jxl_with_exif(cls, name: str) -> Path:
        exif = piexif.dump({"0th": {piexif.ImageIFD.Artist: b"picopt-test"}})
        path = cls.TMP_ROOT / name
        with Image.open(IMAGES_DIR / "test_png.png") as image:
            image.convert("RGB").save(path, "JXL", lossless=True, effort=7, exif=exif)
        return path

    def setup_method(self: "TestJxlMetadata") -> None:
        """Make a clean tmp dir."""
        shutil.rmtree(self.TMP_ROOT, ignore_errors=True)
        self.TMP_ROOT.mkdir(parents=True)

    def teardown_method(self: "TestJxlMetadata") -> None:
        """Remove the tmp dir."""
        shutil.rmtree(self.TMP_ROOT, ignore_errors=True)

    @staticmethod
    def _has_exif(path: Path) -> bool:
        with Image.open(path) as image:
            return bool(image.info.get("exif"))

    def test_metadata_kept_by_default(self: "TestJxlMetadata") -> None:
        """A plain run preserves EXIF."""
        path = self._write_jxl_with_exif("keep.jxl")
        assert self._has_exif(path)
        cli.main((PROGRAM_NAME, "-rq", str(self.TMP_ROOT)))
        assert self._has_exif(path)

    def test_strip_metadata_removes_exif(self: "TestJxlMetadata") -> None:
        """The encoder reads EXIF off the image unless told otherwise."""
        path = self._write_jxl_with_exif("strip.jxl")
        assert self._has_exif(path)
        cli.main((PROGRAM_NAME, "-rqM", str(self.TMP_ROOT)))
        assert not self._has_exif(path)


@pytest.mark.parametrize("fn", ["test_png.png"])
class TestJxlIdempotency(BaseTest):
    """Repeated runs must converge instead of growing the file."""

    TMP_ROOT: Path = get_test_dir()
    SOURCE_DIR: Path = IMAGES_DIR
    FNS: MappingProxyType[str, tuple] = FNS

    def test_repeated_runs_do_not_grow(self: "TestJxlIdempotency", fn: str) -> None:
        """Convert once, then optimize twice more with no change."""
        cli.main((PROGRAM_NAME, "-rvv", "-c", "JXL", str(self.TMP_ROOT)))
        path = (self.TMP_ROOT / fn).with_suffix(".jxl")
        converted = path.read_bytes()

        for _ in range(2):
            cli.main((PROGRAM_NAME, "-rvv", str(self.TMP_ROOT)))
            assert path.stat().st_size <= len(converted)
