"""Test stats module."""
from argparse import Namespace
from pathlib import Path

from picopt import stats
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring

TYPE_NAME = "png"
PATH = Path("dummyPath")


def test_skip() -> None:
    res = stats.skip(TYPE_NAME, PATH)
    assert res.final_path == PATH
    assert res.report_list == [f"Skipping {TYPE_NAME} file: {PATH}"]
    assert res.error is None
    assert not res.nag_about_gifs


def test_humanize_bytes() -> None:
    hum = stats._humanize_bytes(0)
    assert hum == "no bytes"

    hum = stats._humanize_bytes(1)
    assert hum == "1 byte"

    hum = stats._humanize_bytes(1 << int(10))
    assert hum == "1 kiB"

    hum = stats._humanize_bytes(10240)
    assert hum == "10.0 kiB"


def test_new_percent_saved() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(2048, 1024))
    res = stats.new_percent_saved(rep)
    assert res == "50.00% (1 kiB)"

    rep = stats.ReportStats(PATH, bytes_count=(0, 0))
    res = stats.new_percent_saved(rep)
    assert res == "0.00% (0 bytes)"


def test_report_saved() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
    settings = Settings(None, Namespace(verbose=2))
    stats.report_saved(settings, rep)

    settings = Settings(None, Namespace(test=True))
    stats.report_saved(settings, rep)
    # TODO check actual strings


def test_report_totals() -> None:
    settings = Settings(None, Namespace(verbose=2))
    stats.report_totals(settings, 2048, 1024, True, ["a1", "b2"])

    settings = Settings(None, Namespace(test=True))
    stats.report_totals(settings, 2048, 1024, True, ["a1", "b2"])
    # TODO check actual strings
