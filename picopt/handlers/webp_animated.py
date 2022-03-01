from picopt.handlers.handler import Format
from picopt.handlers.webp import WebP


WEBP_ANIMATED_LOSSLESS_FORMAT = Format(WebP.FORMAT_STR, False, True)
WEBP_ANIMATED_LOSSY_FORMAT = Format(WebP.FORMAT_STR, True, True)
