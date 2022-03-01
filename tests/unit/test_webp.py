"""Test webp module."""
import shutil

from pathlib import Path
from typing import Tuple

from picopt.extern import ExtArgs
from picopt.handlers.webp import Gif2WebP, WebPLossless, WebPLossy
from picopt.pillow.webp_lossless import is_lossless
from tests import IMAGES_DIR, get_test_dir


__all__ = ()  # hides module from pydocstring
TMP_DIR = get_test_dir()
WEBP_LOSSLESS_PATH = IMAGES_DIR / "test_webp_lossless.webp"
WEBP_LOSSLESS_PRE_OPTIMIZED_PATH = IMAGES_DIR / "test_webp_lossless_pre-optimized.webp"
WEBP_LOSSY_PATH = IMAGES_DIR / "test_webp_lossy.webp"
WEBP_LOSSY_PRE_OPTIMIZED_PATH = IMAGES_DIR / "test_webp_lossy_pre-optimized.webp"
WEBP_ANIMATED_PATH = IMAGES_DIR / "test_animated_webp.webp"
GIF_PATH = IMAGES_DIR / "test_animated_gif.gif"
TMP_OLD_WEBP_PATH = TMP_DIR / "old.webp"
TMP_OLD_GIF_PATH = TMP_DIR / "old.gif"
PNG_PATH = IMAGES_DIR / "test_png.png"
TMP_OLD_PNG_PATH = TMP_DIR / "old.png"


def _setup(src_path: Path, old_path: Path) -> Tuple[ExtArgs, Path]:
    TMP_DIR.mkdir(exist_ok=True)
    shutil.copy(src_path, old_path)
    new_path = Path(str(old_path.with_suffix(".webp")) + ".picopt-optimized")
    args = ExtArgs(str(old_path), str(new_path), False)
    return args, new_path


def _teardown(_: ExtArgs) -> None:
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)


def _test_convert2webp(
    src_path,
    old_path,
    handler,
    good_old_size,
    good_new_size,
) -> None:
    args, new_path = _setup(src_path, old_path)
    old_size = old_path.stat().st_size
    old_mtime = old_path.stat().st_mtime
    assert old_size == good_old_size
    old_is_lossless = is_lossless(str(old_path))
    program = handler.PROGRAMS[0]
    res = program(args)
    assert res == WebPLossless.SUFFIX
    new_mtime = new_path.stat().st_mtime
    assert new_mtime > old_mtime
    new_is_lossless = is_lossless(str(old_path))
    assert old_is_lossless == new_is_lossless
    new_size = new_path.stat().st_size
    assert new_size == good_new_size
    _teardown(args)


def _test_cwebp(src_path, handler, good_old_size, good_new_size) -> None:
    _test_convert2webp(
        src_path,
        TMP_OLD_WEBP_PATH,
        handler,
        good_old_size,
        good_new_size,
    )


def test_cwebp_lossless() -> None:
    _test_cwebp(WEBP_LOSSLESS_PATH, WebPLossless, 5334, 3870)


def test_cwebp_lossless_pre_optimized() -> None:
    _test_cwebp(WEBP_LOSSLESS_PRE_OPTIMIZED_PATH, WebPLossless, 8914, 8914)


def test_cwebp_lossy() -> None:
    _test_cwebp(WEBP_LOSSY_PATH, WebPLossy, 2764, 1760)


def test_cwebp_lossy_pre_optimized() -> None:
    _test_cwebp(WEBP_LOSSY_PRE_OPTIMIZED_PATH, WebPLossy, 1514, 1514)


# def _test_cwebp_animated() -> None:
#    _test_cwebp(WEBP_ANIMATED_PATH, WebPLossy, 13610, 100)


def test_gif2webp() -> None:
    _test_convert2webp(
        GIF_PATH,
        TMP_OLD_GIF_PATH,
        Gif2WebP,
        16383,
        11846,
    )


def test_png2webp() -> None:
    _test_convert2webp(
        PNG_PATH,
        TMP_OLD_PNG_PATH,
        WebPLossless,
        7967,
        3870,
    )
