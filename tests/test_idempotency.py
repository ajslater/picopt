"""Property tests: optimizing twice is a noop; lossless paths keep pixels."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
IMAGE_FNS = (
    "test_png.png",
    "test_jpg.jpg",
    "test_gif.gif",
    "test_webp_lossless.webp",
)
CBZ_FN = "test_cbz.cbz"
FORMATS_ARG = "PNG,JPEG,GIF,WEBP,CBZ"


def _pixels(path: Path) -> bytes:
    with Image.open(path) as image:
        return image.convert("RGBA").tobytes()


@pytest.fixture(autouse=True)
def _setup_and_teardown() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True)
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


class TestIdempotency:
    """Repeated optimization converges: never grows, fixed by the 2nd pass."""

    def test_optimization_converges(self) -> None:
        for fn in IMAGE_FNS:
            shutil.copy(IMAGES_DIR / fn, TMP_ROOT / fn)
        shutil.copy(CONTAINER_DIR / CBZ_FN, TMP_ROOT / CBZ_FN)
        argv = (PROGRAM_NAME, "-rvx", FORMATS_ARG, str(TMP_ROOT))
        all_fns = (*IMAGE_FNS, CBZ_FN)

        cli.main(argv)
        first = {fn: (TMP_ROOT / fn).read_bytes() for fn in all_fns}

        # A second pass may squeeze a few more bytes out of a multi-tool
        # pipeline (one tool's output enables another), but never grow.
        cli.main(argv)
        second = {fn: (TMP_ROOT / fn).read_bytes() for fn in all_fns}
        for fn in all_fns:
            assert len(second[fn]) <= len(first[fn]), fn

        # By the third pass every file must be at its fixed point.
        cli.main(argv)
        for fn in all_fns:
            assert (TMP_ROOT / fn).read_bytes() == second[fn], fn


class TestPixelIdentity:
    """Lossless optimization and conversion must not change a single pixel."""

    def test_png_optimize_keeps_pixels(self) -> None:
        target = TMP_ROOT / "test_png.png"
        shutil.copy(IMAGES_DIR / "test_png.png", target)
        before = _pixels(target)
        cli.main((PROGRAM_NAME, "-rvx", "PNG", str(TMP_ROOT)))
        assert target.stat().st_size < (IMAGES_DIR / "test_png.png").stat().st_size
        assert _pixels(target) == before

    def test_png_to_webp_conversion_keeps_pixels(self) -> None:
        source = TMP_ROOT / "test_png.png"
        shutil.copy(IMAGES_DIR / "test_png.png", source)
        before = _pixels(source)
        cli.main((PROGRAM_NAME, "-rvx", "PNG,WEBP", "-c", "WEBP", str(TMP_ROOT)))
        converted = TMP_ROOT / "test_png.webp"
        assert converted.is_file()
        assert not source.exists()
        assert _pixels(converted) == before

    def test_gif_to_png_conversion_keeps_pixels(self) -> None:
        source = TMP_ROOT / "test_gif.gif"
        shutil.copy(IMAGES_DIR / "test_gif.gif", source)
        before = _pixels(source)
        cli.main((PROGRAM_NAME, "-rvx", "GIF,PNG", "-c", "PNG", str(TMP_ROOT)))
        converted = TMP_ROOT / "test_gif.png"
        assert converted.is_file()
        assert _pixels(converted) == before
