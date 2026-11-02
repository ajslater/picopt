"""Compatibility shims for older Python versions."""

import sys

if sys.version_info >= (3, 12):
    from typing import override  # pyright: ignore[reportUnreachable]
else:
    from typing_extensions import override

__all__ = ("override",)
