"""
WebP format plugin.

Owns: WebP (still + animated) plus the GIF→WebP and PNG→WebP conversion
routes, split across:

- :mod:`picopt.plugins.webp.tools` — the external cwebp/gif2webp/
  img2webp/webpmux tools and the probed :data:`CWEBP_TOOL` singleton.
- :mod:`picopt.plugins.webp.static` — still :class:`WebPLossless`.
- :mod:`picopt.plugins.webp.animated` — the four animated handlers.

The five WebP handlers cover four different unpack/pack strategies for
the same output format. They are listed in ``Route.convert`` in preference
order; the registry/config layer probes each handler's ``PIPELINE`` and
the routing layer picks the first whose tools are all available.

- :class:`WebPLossless`              still WebP. Stages: optional
                                     PIL→PNG round-trip if input isn't
                                     already cwebp-acceptable, then
                                     cwebp (preferred) or PIL save.

- :class:`Gif2WebPAnimatedLossless`  animated GIF → animated WebP in one
                                     gif2webp invocation (an ImageHandler,
                                     not a container).

- :class:`Img2WebPAnimatedLossless`  container. Frames are written to
                                     disk as lossless WebP via Pillow at
                                     unpack time, then ``img2webp`` packs
                                     the frame files.

- :class:`WebPMuxAnimatedLossless`   container. ``webpmux -get frame``
                                     extracts frames; ``webpmux -frame``
                                     packs them. Only valid for animated
                                     WebP input.

- :class:`PILPackWebPAnimatedLossless`
                                     container. Pure-Pillow fallback;
                                     always available.
"""

from picopt.plugins.base import Handler, Plugin, Route
from picopt.plugins.gif import Gif, GifAnimated
from picopt.plugins.png import Png, PngAnimated
from picopt.plugins.webp.animated import (
    Gif2WebPAnimatedLossless,
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
    WebPAnimatedLossless,
    WebPMuxAnimatedLossless,
)
from picopt.plugins.webp.const import MODERN_CWEBP_FORMATS, WEBP_FORMAT_STR
from picopt.plugins.webp.static import WebPLossless
from picopt.plugins.webp.tools import CWEBP_TOOL, CWebPTool

__all__ = (
    "CWEBP_TOOL",
    "MODERN_CWEBP_FORMATS",
    "PLUGIN",
    "WEBP_FORMAT_STR",
    "CWebPTool",
    "Gif2WebPAnimatedLossless",
    "Img2WebPAnimatedLossless",
    "PILPackWebPAnimatedLossless",
    "WebPAnimatedLossless",
    "WebPLossless",
    "WebPMuxAnimatedLossless",
)

# Convert-target preference for animated-WebP outputs from non-WebP
# inputs (animated GIF, animated PNG). webpmux is intentionally absent —
# it can only read existing animated WebP. img2webp is preferred for
# size; PIL is the always-available fallback.
_ANIMATED_CONVERT_FROM_OTHER: tuple[type[Handler], ...] = (
    Img2WebPAnimatedLossless,
    PILPackWebPAnimatedLossless,
)


PLUGIN = Plugin(
    name="WEBP",
    handlers=(
        WebPLossless,
        Gif2WebPAnimatedLossless,
        Img2WebPAnimatedLossless,
        WebPMuxAnimatedLossless,
        PILPackWebPAnimatedLossless,
    ),
    routes=(
        # Still WebP → still WebPLossless.
        Route(
            file_format=WebPLossless.OUTPUT_FILE_FORMAT,
            native=WebPLossless,
        ),
        Route(
            file_format=Png.OUTPUT_FILE_FORMAT,
            convert=(WebPLossless,),
        ),
        Route(
            file_format=Gif.OUTPUT_FILE_FORMAT,
            convert=(WebPLossless,),
        ),
        # Animated WebP input: webpmux is the natural native handler
        # because it can round-trip without re-encoding via Pillow.
        # Img2Webp / PILPack are listed as convert alternatives so the
        # routing layer can fall back if webpmux is missing.
        Route(
            file_format=WebPMuxAnimatedLossless.OUTPUT_FILE_FORMAT,
            native=WebPMuxAnimatedLossless,
            convert=_ANIMATED_CONVERT_FROM_OTHER,
        ),
        # Convert from animated GIF: prefer gif2webp (purpose-built);
        # fall back to img2webp / PIL via PNG-frame extraction.
        Route(
            file_format=GifAnimated.OUTPUT_FILE_FORMAT,
            convert=(
                Gif2WebPAnimatedLossless,
                *_ANIMATED_CONVERT_FROM_OTHER,
            ),
        ),
        # Convert from animated PNG: img2webp / PIL
        # doesn't read PNG.
        Route(
            file_format=PngAnimated.OUTPUT_FILE_FORMAT,
            convert=_ANIMATED_CONVERT_FROM_OTHER,
        ),
    ),
    convert_targets=(
        WebPLossless,
        Img2WebPAnimatedLossless,
        PILPackWebPAnimatedLossless,
    ),
    default_enabled=True,
)
