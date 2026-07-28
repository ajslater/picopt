"""Test config layering, validation errors, and doctor tier accounting."""

from pathlib import Path
from typing import Any

import pytest
from confuse.exceptions import ConfigError
from typing_extensions import override

from picopt import cli
from picopt.config import PicoptConfig
from picopt.doctor import PicoptDoctor
from picopt.plugins.base.tool import Tool, ToolStatus
from picopt.plugins.jxl import JxlFromJpeg, JxlFromWebP, JxlLossless

__all__ = ()

CONFIG_FILE_VERBOSE = 2


def _get_settings(*args: str):
    return PicoptConfig().get_config(cli.get_arguments(("picopt", *args, ".")))


class TestConfigLayering:
    """Config-file values must not be shadowed by un-passed CLI flags."""

    def test_config_file_booleans_respected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picopt.yaml"
        cfg.write_text("picopt:\n  recurse: true\n  bigger: true\n  verbose: 2\n")
        settings = _get_settings("-C", str(cfg))
        assert settings.recurse is True
        assert settings.bigger is True
        assert settings.verbose == CONFIG_FILE_VERBOSE

    def test_cli_flags_still_override_config_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / "picopt.yaml"
        cfg.write_text("picopt:\n  recurse: false\n  timestamps: false\n")
        settings = _get_settings("-C", str(cfg), "-r", "-t")
        assert settings.recurse is True
        assert settings.timestamps is True

    def test_defaults_without_config_file(self) -> None:
        settings = _get_settings()
        assert settings.recurse is False
        assert settings.bigger is False
        assert settings.verbose == 1
        assert settings.keep_metadata is True
        assert settings.symlinks is True


class TestConfigValidation:
    """Bad values abort at startup with a clean error, not deep in the run."""

    def test_unparseable_memory_limit_aborts(self) -> None:
        with pytest.raises(ConfigError, match="memory-limit"):
            _get_settings("--memory-limit", "banana")

    def test_unparseable_after_aborts(self) -> None:
        with pytest.raises(ConfigError, match="after"):
            _get_settings("-A", "not/a/date/at all")

    def test_no_default_ignores_without_ignore_list_ok(self) -> None:
        settings = _get_settings("-I")
        assert settings.ignore_defaults is False
        assert settings.computed.ignore.case is None
        assert settings.computed.ignore.ignore_case is None

    def test_lowercase_extra_formats_and_convert_to_accepted(self) -> None:
        settings = _get_settings("-x", "zip", "-c", "webp")
        assert "ZIP" in settings.formats
        assert settings.convert_to is not None
        assert "WEBP" in settings.convert_to

    def test_lowercase_jxl_convert_to_accepted(self) -> None:
        settings = _get_settings("-c", "jxl")
        assert settings.convert_to is not None
        assert "JXL" in settings.convert_to


class TestHandlerConfigGate:
    """A handler declaring CONFIG_ENABLED_KEY only runs when the flag is on."""

    def test_gated_handlers_absent_by_default(self) -> None:
        settings = _get_settings("-c", "JXL")
        assert JxlFromJpeg.CONFIG_ENABLED_KEY == "convert_jpeg_to_jxl"
        assert JxlFromWebP.CONFIG_ENABLED_KEY == "convert_webp_to_jxl"
        assert JxlFromJpeg not in settings.computed.handler_stages
        assert JxlFromWebP not in settings.computed.handler_stages
        # The unconditional handler alongside them is still available.
        assert JxlLossless in settings.computed.handler_stages

    def test_jpeg_to_jxl_handler_present_when_enabled(self) -> None:
        settings = _get_settings("-c", "JXL", "--convert-jpeg-to-jxl")
        assert settings.convert_jpeg_to_jxl is True
        assert JxlFromJpeg in settings.computed.handler_stages
        # Each flag gates only its own handler.
        assert JxlFromWebP not in settings.computed.handler_stages

    def test_webp_to_jxl_handler_present_when_enabled(self) -> None:
        settings = _get_settings("-c", "JXL", "--convert-webp-to-jxl")
        assert settings.convert_webp_to_jxl is True
        assert JxlFromWebP in settings.computed.handler_stages
        assert JxlFromJpeg not in settings.computed.handler_stages


class _FakeTool(Tool):
    """Probe-only tool with a fixed availability."""

    def __init__(self, name: str, *, available: bool, required: bool = True) -> None:
        self.name = name
        self.required = required
        self._available = available

    @override
    def probe_version(self) -> str:
        return "1.0"

    @override
    def probe(self) -> ToolStatus:
        return ToolStatus(
            name=self.name, available=self._available, required=self.required
        )


class _CountingTool(Tool):
    """Tool counting how many real probes run."""

    name = "counting-tool"

    def __init__(self) -> None:
        self.probes = 0

    @override
    def probe_version(self) -> str:
        return "1.0"

    @override
    def _probe(self) -> ToolStatus:
        self.probes += 1
        return ToolStatus(name=self.name, available=True)


class TestProbeMemoization:
    """probe() runs the real probe once per instance."""

    def test_probe_is_cached(self: Any) -> None:
        tool = _CountingTool()
        first = tool.probe()
        second = tool.probe()
        assert tool.probes == 1
        assert first is second


class TestDoctorTierAccounting:
    """Tools in a tier are alternatives; one available tool satisfies it."""

    def test_tier_with_one_available_alternative_is_healthy(self: Any) -> None:
        doctor = PicoptDoctor()
        tier = (
            _FakeTool("missing-tool", available=False),
            _FakeTool("present-tool", available=True),
        )
        doctor._checkup_handler_pipeline_tier(0, tier)
        assert doctor.total_required == 1
        assert doctor.missing_required == 0

    def test_tier_with_no_available_tool_is_missing(self: Any) -> None:
        doctor = PicoptDoctor()
        tier = (
            _FakeTool("gone-a", available=False),
            _FakeTool("gone-b", available=False),
        )
        doctor._checkup_handler_pipeline_tier(0, tier)
        assert doctor.total_required == 1
        assert doctor.missing_required == 1

    def test_all_optional_tier_never_required(self: Any) -> None:
        doctor = PicoptDoctor()
        tier = (_FakeTool("extra", available=False, required=False),)
        doctor._checkup_handler_pipeline_tier(0, tier)
        assert doctor.total_required == 0
        assert doctor.missing_required == 0
        assert doctor.missing_optional == 1
