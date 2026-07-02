"""
SVG format plugin.

Owns: SVG. Tool: svgo, as a binary or via bunx/npx.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, BinaryIO

from typing_extensions import override

from picopt.plugins.base import (
    BunxTool,
    Detector,
    ExternalTool,
    Handler,
    ImageHandler,
    NpxTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import SVG_FORMAT_STR, FileFormat

if TYPE_CHECKING:
    from io import BytesIO

    from picopt.path import PathInfo

_SVGO_ARGS: tuple[str, ...] = ("--output", "-", "--input", "-")

# svgo's default preset is not lossless: removeViewBox breaks responsive
# scaling, and several plugins strip metadata the user asked to keep. svgo
# v2+ only accepts plugin configuration through a config file, so ship two
# explicit variants. CommonJS (.cjs) parses under both node and bun.
_SVGO_STRIP_METADATA_PLUGINS = """
    "removeMetadata",
    "removeTitle",
    "removeDesc",
"""
_SVGO_CONFIG_TEMPLATE = """module.exports = {{
  multipass: true,
  plugins: [
    {{
      name: "preset-default",
      params: {{
        overrides: {{
          removeViewBox: false,
          removeMetadata: false,
          removeTitle: false,
          removeDesc: false,
        }},
      }},
    }},{extra_plugins}
  ],
}};
"""

_svgo_config_cache: dict[bool, Path] = {}


def _svgo_config_path(*, keep_metadata: bool) -> Path:
    """Return a per-process temp config file for the metadata policy."""
    path = _svgo_config_cache.get(keep_metadata)
    if path is None or not path.exists():
        extra_plugins = "" if keep_metadata else _SVGO_STRIP_METADATA_PLUGINS
        content = _SVGO_CONFIG_TEMPLATE.format(extra_plugins=extra_plugins)
        with NamedTemporaryFile(
            "w", prefix="picopt_svgo_", suffix=".config.cjs", delete=False
        ) as config_file:
            config_file.write(content)
            path = Path(config_file.name)
        _svgo_config_cache[keep_metadata] = path
    return path


class _SvgoMixin:
    """Shared run_stage so the binary and the npx variants share invocation."""

    def run_stage(self, handler: Handler, buf: BinaryIO) -> BytesIO:
        config_path = _svgo_config_path(keep_metadata=handler.config.keep_metadata)
        return Handler.run_ext(
            (
                *self.exec_args(),  # pyright:ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
                "--config",
                str(config_path),
                *_SVGO_ARGS,
            ),
            buf,
        )


class SvgoTool(_SvgoMixin, ExternalTool):
    """svgo installed as a global binary."""

    name = "svgo"
    binary = "svgo"


class BunxSvgoTool(_SvgoMixin, BunxTool):
    """svgo run via bunx (no global install needed)."""

    name = "bunx_svgo"
    bunx_name = "svgo"


class NpxSvgoTool(_SvgoMixin, NpxTool):
    """svgo run via npx (no global install needed)."""

    name = "npx_svgo"
    npx_name = "svgo"


class SvgDetector(Detector):
    """SVG identification: just look at the suffix."""

    PRIORITY: int = 0

    @override
    @classmethod
    def identify(cls: type[SvgDetector], path_info: PathInfo) -> FileFormat | None:
        return Svg.OUTPUT_FILE_FORMAT if path_info.suffix().lower() == ".svg" else None


class Svg(ImageHandler):
    """SVG handler."""

    OUTPUT_FORMAT_STR = SVG_FORMAT_STR
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, lossless=True, animated=False)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    SUFFIXES: tuple[str, ...] = (".svg",)
    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (SvgoTool(), BunxSvgoTool(), NpxSvgoTool()),
    )


PLUGIN = Plugin(
    name=SVG_FORMAT_STR,
    handlers=(Svg,),
    routes=(Route(file_format=Svg.OUTPUT_FILE_FORMAT, native=Svg),),
    detector=SvgDetector,
    default_enabled=False,
)
