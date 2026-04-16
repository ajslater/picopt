"""Tests init."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

import inspect
from pathlib import Path

TEST_FILES_DIR = Path("tests/test_files")
IMAGES_DIR = TEST_FILES_DIR / "images"
INVALID_DIR = TEST_FILES_DIR / "invalid"
CONTAINER_DIR = TEST_FILES_DIR / "containers"
TMP_ROOT = "/tmp"  # noqa: S108

# Default tolerance for output size comparisons. Optimization tools (mozjpeg,
# oxipng, cwebp, lzma, bz2, etc.) and their underlying libraries (libpng,
# libwebp, zlib) produce slightly different byte counts across versions and
# platforms even for identical inputs. The defaults below are loose enough to
# absorb the linux/darwin platform splits we've observed in CI plus normal
# tool-version drift, while still catching real regressions.
DEFAULT_SIZE_TOLERANCE_PCT = 0.05
DEFAULT_SIZE_TOLERANCE_MIN_BYTES = 64


def assert_size_close(
    actual: int,
    expected: int,
    *,
    pct: float = DEFAULT_SIZE_TOLERANCE_PCT,
    min_bytes: int = DEFAULT_SIZE_TOLERANCE_MIN_BYTES,
) -> None:
    """
    Assert that ``actual`` is within tolerance of ``expected``.

    Tolerance is ``max(expected * pct, min_bytes)`` so that very small files
    still get a useful absolute floor and large files scale proportionally.
    """
    tolerance = max(int(expected * pct), min_bytes)
    diff = abs(actual - expected)
    assert diff <= tolerance, (
        f"size {actual} differs from expected {expected} by {diff} bytes "
        f"(tolerance ±{tolerance})"
    )


def get_test_dir() -> "pathlib.PosixPath":
    """Return a module specific tmpdir."""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        caller = frame.f_back
        module_name = caller.f_globals["__name__"]
    else:
        module_name = "unknown"

    return TMP_ROOT / Path("picopt-" + module_name)
