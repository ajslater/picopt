"""The recorded timestamps config defaults must match a real default run."""

import os

import pytest
from treestamps.tree.config import TreestampsConfig

from picopt import PROGRAM_NAME, cli
from picopt.config import PicoptConfig
from picopt.config.consts import (
    RETIRED_TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_DEFAULTS,
    TIMESTAMPS_CONFIG_KEYS,
)

__all__ = ()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path) -> None:  # pyright: ignore[reportUnusedFunction]
    """Scrub env and isolate the user config so defaults really are defaults."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PICOPTDIR", str(tmp_path))


class TestTimestampsConfigDefaults:
    """Guard the defaults map against drift."""

    def test_covers_exactly_the_recorded_keys(self) -> None:
        """Every recorded key needs a default; nothing else belongs."""
        assert set(TIMESTAMPS_CONFIG_DEFAULTS) == set(TIMESTAMPS_CONFIG_KEYS)

    def test_retired_keys_are_no_longer_recorded(self) -> None:
        """A key cannot be both recorded and retired."""
        assert not set(RETIRED_TIMESTAMPS_CONFIG_DEFAULTS) & set(TIMESTAMPS_CONFIG_KEYS)

    def test_match_a_resolved_default_run(self, tmp_path) -> None:
        """
        The defaults must equal what a bare run actually resolves.

        Treestamps treats a key missing from a stamp file as holding its
        default, so a default that drifts from the resolved value would
        either wrongly keep or wrongly discard old stamp files.
        """
        args = cli.get_arguments((PROGRAM_NAME, str(tmp_path)))
        settings = PicoptConfig().get_config(args)
        resolved = {key: getattr(settings, key) for key in TIMESTAMPS_CONFIG_KEYS}
        assert TreestampsConfig.normalize_config(
            resolved
        ) == TreestampsConfig.normalize_config(dict(TIMESTAMPS_CONFIG_DEFAULTS))
