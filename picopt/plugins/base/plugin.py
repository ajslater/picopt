"""
Plugin descriptors used to register a format with the registry.

Each plugin module under picopt/plugins/ exposes a module-level ``PLUGIN``
constant of type :class:`Plugin`. The registry walks the plugins package on
import, collects every PLUGIN, and from those builds the runtime tables that
the rest of picopt needs (the format → handler routing map, the list of
advertised --convert-to targets, the set of lossless format strings, the
PIL-convertible format set, the doctor command's tool inventory, etc.).

This is the *only* place these tables come from. There is no parallel
hand-maintained list anywhere else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picopt.path import PathInfo
    from picopt.plugins.base.format import FileFormat
    from picopt.plugins.base.handler import Handler


class Detector(ABC):
    """
    A non-PIL format detector contributed by a plugin.

    Plugins for formats that PIL can't identify (archives, SVG) provide a
    detector. Plugins for PIL-handled formats can leave ``Plugin.detector``
    as ``None``; PIL handles their identification automatically.

    Detectors run in ``priority`` order (highest first). Order matters for
    overlapping signatures: ``TarGz``/``TarBz``/``TarXz`` must run before
    ``Tar`` because plain ``is_tarfile`` matches all of them. Make ``Tar``'s
    detector lower-priority and the constraint lives next to ``Tar`` instead
    of in the dispatcher.
    """

    PRIORITY: int = 0

    @classmethod
    @abstractmethod
    def identify(cls, path_info: PathInfo) -> FileFormat | None:
        """Return a FileFormat if this detector recognises the path, else None."""


@dataclass(frozen=True)
class Route:
    """
    A routing entry: how to handle one input FileFormat.

    ``native`` is the handler that optimizes the format in place (same input
    and output format). ``convert`` is an ordered tuple of handlers that can
    convert *from* this format to their own output format; the first one
    whose required tools are available wins, but only if the user has asked
    for that conversion via ``--convert-to``.
    """

    file_format: FileFormat
    native: type[Handler] | None = None
    convert: tuple[type[Handler], ...] = ()


@dataclass(frozen=True)
class Plugin:
    """
    One format's complete contribution to picopt.

    Attributes:
        name: Uppercase identifier, conventionally the OUTPUT_FORMAT_STR of
            the plugin's primary handler. Shown in the doctor command and
            error messages.
        handlers: Every Handler subclass this plugin owns. The doctor walks
            this for tool probing.
        routes: Format → handler routing entries. A plugin contributes one
            Route per FileFormat it knows how to receive as input. Other
            plugins may contribute their own Routes for the same FileFormat;
            the registry merges them.
        convert_targets: Handlers from this plugin that should be advertised
            to the user as valid ``--convert-to`` choices.
        detector: Optional non-PIL detector. Leave as None for PIL-handled
            formats.
        default_enabled: Whether this format is on by default. Mirrors the
            old DEFAULT_HANDLERS set.
        input_only: True for formats picopt can read but not write (RAR).
            These never appear in --convert-to and are excluded from the
            "all output formats" set.

    """

    name: str
    handlers: tuple[type[Handler], ...] = ()
    routes: tuple[Route, ...] = ()
    convert_targets: tuple[type[Handler], ...] = ()
    detector: type[Detector] | None = None
    default_enabled: bool = False
    input_only: bool = False
    # Extra format strings this plugin "owns" beyond its handlers'
    # OUTPUT_FORMAT_STR. Used by the PIL-convertible plugin to claim BMP,
    # PCX, etc as known input format strings without owning a handler for
    # them.
    extra_format_strs: frozenset[str] = field(default_factory=frozenset)
