"""
Tool hierarchy.

A Tool is a discoverable, probeable unit of optimization work. It owns:

1. **Probing**: ``probe()`` returns a :class:`ToolStatus` reporting whether
   the tool is available, its version, and (optionally) where it lives. This
   is what the ``picopt doctor`` command consumes.

2. **Invocation**: handler optimization stages call ``run_stage(handler, buf)``
   to transform a buffer. Container packing calls ``run_pack(handler)`` to
   build the final packed buffer from already-optimized contents. Tool
   subclasses implement whichever they support.

Tools are arranged in a handler's ``PIPELINE``:

    PIPELINE: tuple[tuple[Tool, ...], ...] = (
        (PILSaveTool(...),),                     # tier 1: one alternative
        (OxiPngTool(), PngOutTool()),            # tier 2: oxipng preferred
    )

Each outer tuple is a sequential pipeline tier; every tier must produce a
selected tool or the handler is unusable. Each inner tuple is the alternatives
for that tier; the first whose ``probe()`` returns available wins. This is
exactly the shape of the old ``PROGRAMS`` attribute, just typed.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import version as module_version
from pathlib import Path
from platform import python_version
from typing import TYPE_CHECKING, BinaryIO

from typing_extensions import override

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(frozen=True)
class ToolStatus:
    """Result of probing a tool."""

    name: str
    available: bool
    version: str = ""
    path: str = ""
    error: str = ""
    required: bool = True


class Tool(ABC):
    """
    Abstract base for an optimization tool.

    A subclass must override at least ``probe`` and one of ``run_stage`` or
    ``run_pack``. ``required=False`` marks the tool as optional within its
    tier; the doctor command surfaces missing optional tools differently
    from missing required ones.
    """

    name: str = ""
    required: bool = True

    def parse_version(self, version: str) -> str:
        """Override to parse tool version specially."""
        return version

    @abstractmethod
    def probe_version(self) -> str:
        """Probe the tool version for probe()."""

    @abstractmethod
    def probe(self) -> ToolStatus:
        """Return availability, version, and path."""

    def run_stage(self, handler, buf: BinaryIO) -> BinaryIO:
        """Transform an input buffer; default raises."""
        msg = f"{type(self).__name__} does not implement run_stage"
        raise NotImplementedError(msg)

    def run_pack(self, handler) -> BinaryIO:
        """Pack already-optimized container contents; default raises."""
        msg = f"{type(self).__name__} does not implement run_pack"
        raise NotImplementedError(msg)

    def exec_args(self) -> tuple[str, ...]:
        """Discovered argv prefix for external tools; () for everything else."""
        return ()


# ---------------------------------------------------------------------------
# Built-in tool flavours
# ---------------------------------------------------------------------------


class InternalTool(Tool):
    """
    A tool implemented as a Python library import.

    Subclasses set ``name`` and ``module_name``. Probing imports the module
    and reads its ``__version__``. The optimization logic lives in the
    subclass's ``run_stage``.
    """

    module_name: str = ""
    PACKAGE_NAME: str = ""

    @override
    def probe_version(self) -> str:
        package_name = self.PACKAGE_NAME or self.module_name
        version = module_version(package_name) if package_name else "builtin"
        return self.parse_version(version)

    def probe_path(self, module: ModuleType) -> str:
        """Probe the intermal module path."""
        return getattr(module, "__file__", "") or "<builtin>"

    @override
    def probe(self) -> ToolStatus:
        """Return results for doctor."""
        try:
            module = __import__(self.module_name)
        except ImportError as exc:
            return ToolStatus(
                name=self.name,
                available=False,
                error=str(exc),
                required=self.required,
            )

        version = self.probe_version()
        path = self.probe_path(module)

        return ToolStatus(
            name=self.name,
            available=True,
            version=version,
            path=path,
            required=self.required,
        )


class StdLibTool(InternalTool):
    """A tool taken from the Python Standard Library."""

    PYTHON_VERSION = f"Python {python_version()}"

    @override
    def probe_version(self) -> str:
        """Return Python version."""
        return self.PYTHON_VERSION

    @override
    def probe_path(
        self,
        module: ModuleType | None = None,
    ) -> str:
        """Return placeholder."""
        return "<stdlib>"


class PILSaveTool(InternalTool):
    """A tool that uses PIL to convert/save the buffer to a target format."""

    name: str = "pil"
    module_name = "PIL"
    PACKAGE_NAME = "Pillow"

    def __init__(
        self,
        target_format_str: str = "",
        save_kwargs: dict | None = None,
        name: str = "",
    ) -> None:
        """Initialize instance vars."""
        if name:
            self.name = name
            # if target_format_str:
        self.target_format_str = target_format_str
        # if save_kwargs is not None:
        self.save_kwargs = save_kwargs

    @override
    def run_stage(self, handler, buf: BinaryIO) -> BinaryIO:
        # Defer to the handler's pil_save helper for the actual save call.
        # The handler decides whether the buffer is already in an acceptable
        # format and short-circuits if so.
        image_handler = handler
        target = self.target_format_str or image_handler.OUTPUT_FORMAT_STR
        opts = (
            self.save_kwargs
            if self.save_kwargs is not None
            else image_handler.PIL2_KWARGS
        )
        return image_handler.pil_save(buf, format_str=target, opts=opts)


class ExternalTool(Tool):
    """A tool that lives on the filesystem and is invoked via subprocess."""

    binary: str = ""
    version_args: tuple[str, ...] = ("--version",)
    version_line: int = 0

    def __init__(self) -> None:
        """Init cached path."""
        self._cached_path: Path | None | object = _UNSET

    def _path(self) -> Path | None:
        if self._cached_path is _UNSET:
            found = shutil.which(self.binary or self.name)
            self._cached_path = Path(found) if found else None
        return self._cached_path  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]

    @override
    def parse_version(self, version: str) -> str:
        """Take version from first line of external tool output."""
        return version.splitlines()[self.version_line].strip()

    @override
    def probe_version(self, path: str = "") -> str:
        version = ""
        try:
            if not path:
                raise ValueError
            result = subprocess.run(  # noqa: S603
                (path, *self.version_args),
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = result.stdout or result.stderr
            version = self.parse_version(version)
        except (subprocess.SubprocessError, OSError, IndexError):
            pass
        return version

    @override
    def probe(self) -> ToolStatus:
        """Doctor probe."""
        path = self._path()
        if path is None:
            return ToolStatus(
                name=self.name,
                available=False,
                error=f"{self.binary or self.name} not found in PATH",
                required=self.required,
            )
        version = self.probe_version(str(path))
        return ToolStatus(
            name=self.name,
            available=True,
            version=version,
            path=str(path),
            required=self.required,
        )

    @override
    def exec_args(self) -> tuple[str, ...]:
        """Args for exec."""
        path = self._path()
        return (str(path),) if path is not None else ()


class NpxTool(ExternalTool):
    """A tool installed via npm and invoked through ``npx --no``."""

    npx_name: str = ""

    @override
    def _path(self) -> Path | None:
        if self._cached_path is not _UNSET:
            return self._cached_path  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]
        npx = shutil.which("npx")
        if not npx:
            self._cached_path = None
            return None
        # The only reliable way to know if an npx package is installed is to
        # try to run it. ``--no`` prevents npx from helpfully downloading it.
        try:
            subprocess.run(  # noqa: S603
                (npx, "--no", self.npx_name or self.name, "--version"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            self._cached_path = None
            return None
        npx_path = Path(npx)
        self._cached_path = npx_path
        return npx_path

    @override
    def exec_args(self) -> tuple[str, ...]:
        """Args for subprocess."""
        path = self._path()
        return (
            (str(path), "--no", self.npx_name or self.name) if path is not None else ()
        )


class BunxTool(ExternalTool):
    """A tool installed via bun and invoked through ``bunx --no-install``."""

    bunx_name: str = ""

    @override
    def _path(self) -> Path | None:
        if self._cached_path is not _UNSET:
            return self._cached_path  # pyright: ignore[reportReturnType], # ty: ignore[invalid-return-type]
        bunx = shutil.which("bunx")
        if not bunx:
            self._cached_path = None
            return None
        # ``--no-install`` is bunx's equivalent of ``npx --no``: fail rather
        # than silently downloading a package that isn't already present.
        try:
            subprocess.run(  # noqa: S603
                (bunx, "--no-install", self.bunx_name or self.name, "--version"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            self._cached_path = None
            return None
        bunx_path = Path(bunx)
        self._cached_path = bunx_path
        return bunx_path

    @override
    def exec_args(self) -> tuple[str, ...]:
        """Args for subprocess."""
        path = self._path()
        return (
            (str(path), "--no-install", self.bunx_name or self.name)
            if path is not None
            else ()
        )


# Sentinel for "not yet probed".
_UNSET: object = object()
