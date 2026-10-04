"""A same-format handler stands in for an unavailable native handler."""

import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.config import PicoptConfig
from picopt.config.handlers import formats_summary
from picopt.plugins.base import Handler
from picopt.plugins.webp.animated import (
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
    WebPMuxAnimatedLossless,
)
from picopt.walk.walk import Walk
from tests import IMAGES_DIR

__all__ = ()

_ANIMATED_WEBP = WebPMuxAnimatedLossless.OUTPUT_FILE_FORMAT
_ALL = (WebPMuxAnimatedLossless, Img2WebPAnimatedLossless, PILPackWebPAnimatedLossless)
_NO_CONVERT: frozenset[str] = frozenset()


def _pick(
    available: Iterable[type[Handler]],
    *,
    convert_to: frozenset[str] = _NO_CONVERT,
    repack: bool = False,
) -> type[Handler] | None:
    native, convert_chain = registry.routes_by_format()[_ANIMATED_WEBP]
    return registry.pick_route_handler(
        _ANIMATED_WEBP,
        native,
        convert_chain,
        convert=True,
        repack=repack,
        convert_to=convert_to,
        handler_stages=dict.fromkeys(available, ()),
    )


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (_ALL, WebPMuxAnimatedLossless),
        (_ALL[1:], Img2WebPAnimatedLossless),
        (_ALL[2:], PILPackWebPAnimatedLossless),
        ((), None),
    ],
)
@pytest.mark.parametrize("repack", [False, True])
def test_native_then_stand_ins(
    available: tuple[type[Handler], ...],
    expected: type[Handler] | None,
    *,
    repack: bool,
) -> None:
    assert _pick(available, repack=repack) is expected


def test_convert_pick_unchanged() -> None:
    """-c WEBP still picks from the convert chain before the native."""
    assert _pick(_ALL, convert_to=frozenset({"WEBP"})) is Img2WebPAnimatedLossless


def test_convert_only_format_gets_no_stand_in() -> None:
    _, convert_chain = registry.routes_by_format()[_ANIMATED_WEBP]
    picked = registry.pick_route_handler(
        _ANIMATED_WEBP,
        None,
        convert_chain,
        convert=True,
        repack=False,
        convert_to=_NO_CONVERT,
        handler_stages=dict.fromkeys(_ALL, ()),
    )
    assert picked is None


def test_stand_in_is_not_a_conversion() -> None:
    stages = {PILPackWebPAnimatedLossless: ()}
    [route] = [
        route
        for route in formats_summary(frozenset({"WEBP"}), _NO_CONVERT, stages)
        if route.file_format == _ANIMATED_WEBP
    ]
    assert route.picked is PILPackWebPAnimatedLossless
    assert not route.converts


def test_walk_optimizes_without_webpmux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PICOPTDIR", str(tmp_path / "config"))
    path = tmp_path / "animated.webp"
    shutil.copy(IMAGES_DIR / "test_animated_webp.webp", path)
    arguments = cli.get_arguments(
        (PROGRAM_NAME, "-q", "-D", "webpmux,img2webp", str(path))
    )
    settings = PicoptConfig().get_config(arguments)
    assert WebPMuxAnimatedLossless not in settings.computed.handler_stages
    stats = Walk(settings).walk()
    assert not stats.errors
    assert stats.skipped == 0
    assert stats.bytes_in == path.stat().st_size
