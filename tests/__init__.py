"""Tests init."""
import inspect
from pathlib import Path

TEST_FILES_DIR = Path("tests/test_files")
IMAGES_DIR = TEST_FILES_DIR / "images"
INVALID_DIR = TEST_FILES_DIR / "invalid"
CONTAINER_DIR = TEST_FILES_DIR / "containers"
TMP_ROOT = "/tmp"  # noqa


def get_test_dir():
    """Return a module specific tmpdir."""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        caller = frame.f_back
        module_name = caller.f_globals["__name__"]
    else:
        module_name = "unknown"

    return TMP_ROOT / Path("picopt-" + module_name)
