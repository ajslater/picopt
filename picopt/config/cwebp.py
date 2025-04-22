"""CWebP config."""

import subprocess

from picopt.handlers.image.webp import WebPLossless

# cwebp before this version only accepts PNG & WEBP
MIN_CWEBP_VERSION = (1, 2, 3)


def _get_cwebp_version(handler_stages: dict):
    """Get the version of cwebp."""
    cwebp_version = ""
    bin_path = handler_stages.get(WebPLossless, {}).get("cwebp")
    if not bin_path:
        return cwebp_version
    args = (*bin_path, "-version")
    result = subprocess.run(  # noqa: S603
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    if result.returncode == 0:
        cwebp_version = result.stdout.splitlines()[0].strip()
    return cwebp_version


def is_cwebp_modern(handler_stages: dict) -> tuple[bool, str]:
    """Return if cwebp is a modern version."""
    cwebp_version = "Unknown"
    try:
        cwebp_version = _get_cwebp_version(handler_stages)
        if not cwebp_version:
            return False, cwebp_version
        parts = cwebp_version.split(".")
        for index in range(len(MIN_CWEBP_VERSION)):
            test_part = int(parts[index])
            ref_part = MIN_CWEBP_VERSION[index]
            if test_part > ref_part:
                return True, cwebp_version
            if test_part < ref_part:
                return False, cwebp_version
    except Exception:
        return False, cwebp_version
    return True, cwebp_version
