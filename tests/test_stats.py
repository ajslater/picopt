"""Test stats commands."""
from pathlib import Path

from picopt import stats


__all__ = ()  # hides module from pydocstring

TYPE_NAME = "png"
PATH = Path("dummyPath")


def test_skip():
    res = stats.skip(TYPE_NAME, PATH)
    assert res.final_path == PATH
    assert res.report_list == [f"Skipping {TYPE_NAME} file: {PATH}"]
    assert res.error is None
    assert not res.nag_about_gifs


def test_humanize_bytes():
    hum = stats._humanize_bytes(0)
    assert hum == "no bytes"

    hum = stats._humanize_bytes(1)
    assert hum == "1 byte"

    hum = stats._humanize_bytes(1 << int(10))
    assert hum == "1 kiB"

    hum = stats._humanize_bytes(10240)
    assert hum == "10.0 kiB"


def test_new_percent_saved():
    rep = stats.ReportStats(PATH, bytes_count=(2048, 1024))
    res = stats.new_percent_saved(rep)
    assert res == "50.00% (1 kiB)"

    rep = stats.ReportStats(PATH, bytes_count=(0, 0))
    res = stats.new_percent_saved(rep)
    assert res == "0.00% (0 bytes)"
