"""
Regression tests for img2webp frame-duration argument building.

img2webp rejects any ``-d`` value <= 0 with "Invalid negative duration",
which aborts the whole animated-WebP repack. Some sources carry 0ms frame
durations, so :meth:`Img2WebPAnimatedLossless.img2webp_args` must clamp
each duration up to img2webp's 1ms minimum.
"""

from pathlib import Path

from picopt import cli
from picopt.config import PicoptConfig
from picopt.plugins.webp.animated import Img2WebPAnimatedLossless

__all__ = ()


def _make_handler(durations: tuple[int, ...]) -> Img2WebPAnimatedLossless:
    """Build a handler bypassing __init__, with only what img2webp_args reads."""
    handler = Img2WebPAnimatedLossless.__new__(Img2WebPAnimatedLossless)
    handler.config = PicoptConfig().get_config(cli.get_arguments(("picopt", ".")))
    handler.frame_info = {"duration": durations}
    handler._frame_paths = [
        Path(f"frame_{i:02d}.webp") for i in range(1, len(durations) + 1)
    ]
    return handler


def _durations_in_args(args: tuple[str, ...]) -> list[str]:
    return [args[i + 1] for i, tok in enumerate(args) if tok == "-d"]


class TestImg2WebPDurationClamp:
    """Zero and negative frame durations must be clamped to img2webp's minimum."""

    def test_zero_durations_clamped_to_one(self) -> None:
        args = _make_handler((0, 0, 100)).img2webp_args()
        assert "-d" in args
        assert "0" not in _durations_in_args(args)
        assert _durations_in_args(args) == ["1", "1", "100"]

    def test_negative_duration_clamped(self) -> None:
        args = _make_handler((-5, 50)).img2webp_args()
        assert _durations_in_args(args) == ["1", "50"]

    def test_positive_durations_unchanged(self) -> None:
        args = _make_handler((40, 60, 80)).img2webp_args()
        assert _durations_in_args(args) == ["40", "60", "80"]
