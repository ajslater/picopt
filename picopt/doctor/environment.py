"""
The environment header: what a bug report needs, never a verdict.

Uses only the standard library and Pillow's feature table, so it prints
even when plugin discovery later fails.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Final

from rich.text import Text

from picopt import PROGRAM_NAME, get_version
from picopt.log import console

_DOCKERENV: Final = Path("/.dockerenv")
_ENV_PREFIX: Final = f"{PROGRAM_NAME.upper()}_"
_CONFIG_DIR_VAR: Final = f"{PROGRAM_NAME.upper()}DIR"
# Encoder libraries whose versions explain output differences between
# machines. libjpeg-turbo needs version_feature(): features.version("jpg")
# returns the libjpeg ABI version, 6.2, which says nothing.
_PIL_MODULES: Final = (("libwebp", "webp"), ("zlib", "zlib"), ("libavif", "avif"))
_PIL_FEATURES: Final = (("libjpeg-turbo", "libjpeg_turbo"),)
_UNKNOWN: Final = "?"


def _pillow_version(getter_name: str, name: str) -> str:
    """One Pillow library version; "?" if Pillow can't say."""
    try:
        from PIL import features

        version = getattr(features, getter_name)(name)
    except Exception:
        return _UNKNOWN
    return str(version) if version else "missing"


def _pillow_line() -> str:
    try:
        from PIL import __version__ as pillow_version
    except Exception:
        return "Pillow: unavailable"
    libs = [
        f"{label} {_pillow_version('version_feature', name)}"
        for label, name in _PIL_FEATURES
    ]
    libs += [
        f"{label} {_pillow_version('version', name)}" for label, name in _PIL_MODULES
    ]
    return f"Pillow {pillow_version}: " + " · ".join(libs)


def _program_line() -> str:
    python = f"Python {platform.python_version()} ({sys.executable})"
    parts = [f"{PROGRAM_NAME} {get_version()}", python, platform.platform()]
    if _DOCKERENV.exists():
        parts.append("in Docker")
    return " · ".join(parts)


def _env_line() -> str:
    """Names, not values, of picopt's env vars: values may be private."""
    names = sorted(name for name in os.environ if name.startswith(_ENV_PREFIX))
    if config_dir := os.environ.get(_CONFIG_DIR_VAR):
        names.append(f"{_CONFIG_DIR_VAR}={config_dir}")
    return "Environment: " + ", ".join(names) if names else ""


def environment_lines() -> tuple[str, ...]:
    """Return the header lines."""
    return tuple(
        line for line in (_program_line(), _pillow_line(), _env_line()) if line
    )


def render_environment() -> None:
    """Print the header."""
    for line in environment_lines():
        # Text, not markup: paths can hold brackets.
        console.print(Text(line))
    console.print()
