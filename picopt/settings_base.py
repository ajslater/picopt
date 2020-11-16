"""Settings class for picopt."""
from abc import ABC
from argparse import Namespace
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML


class SettingsBase(Namespace, ABC):
    """Global settings base class."""

    _YAML = YAML()

    @property
    @classmethod
    def _RC_NAME(cls):  # noqa: N802
        """Children must implement the _RC_NAME."""
        raise NotImplementedError()

    def __init__(
        self,
        arg_namespace: Optional[Namespace] = None,
        rc_path: Optional[Path] = None,
        check_programs: bool = False,
    ) -> None:
        """Initialize settings object with arguments namespace."""
        self.arg_namespace = arg_namespace
        if check_programs:
            # only do this once for the whole system
            self._config_program_reqs()
        self.load_settings(rc_path)

    def clone(self, path: Path):
        """Clone this settings for a new path."""
        return type(self)(self.arg_namespace, path)

    def _update(self, namespace: Optional[Namespace]) -> None:
        """Update settings with a dict."""
        if not namespace:
            return
        for key, val in namespace.__dict__.items():
            if key.startswith("_"):
                continue
            setattr(self, key, val)

    def load_settings(self, path: Optional[Path]) -> None:
        """Load settings for a path."""
        if path is not None:
            rc_namespace = self.load_rc(path)
            # rc settings write over defaulst
            self._update(rc_namespace)
        # passed in args overwrite rc
        self._update(self.arg_namespace)

    def load_rc(self, path: Path) -> Namespace:
        """Load an rc file, searching recursively upwards."""
        if path.is_file():
            path = path.parent

        rc_path = path / self._RC_NAME

        if rc_path.is_file():
            try:
                rc_settings = self._YAML.load(rc_path)
                for attr in self._SET_ATTRS:
                    attr_list = rc_settings.get(attr)
                    if attr_list is not None:
                        rc_settings[attr] = set(attr_list)
                return Namespace(**rc_settings)
            except Exception as exc:
                print(f"Error parsing {rc_path}")
                print(exc)

        if path == path.parent:
            # at root /, no rc found.
            res = Namespace()
        else:
            res = self.load_rc(path.parent)

        return res
