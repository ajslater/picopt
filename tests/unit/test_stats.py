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


def test_humanize_bytes_none() -> None:
    hum = stats._humanize_bytes(0)
    assert hum == "no bytes"


def test_humanize_bytes_1() -> None:
    hum = stats._humanize_bytes(1)
    assert hum == "1 byte"


def test_humanize_bytes_1kb() -> None:
    hum = stats._humanize_bytes(1 << int(10))
    assert hum == "1 kiB"


def test_humanize_bytes_10kb() -> None:
    hum = stats._humanize_bytes(10240)
    assert hum == "10.0 kiB"


def test_humanize_bytes_huge() -> None:
    hum = stats._humanize_bytes(1 << int(60))
    assert hum == "1024.0 PiB"


def test_humanize_bytes_neg() -> None:
    hum = stats._humanize_bytes(-10240)
    assert hum == "-10.0 kiB"


def test_new_percent_saved_50() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(2048, 1024))
    res = stats.new_percent_saved(rep)
    assert res == "50.00% (1 kiB)"


def test_new_percent_saved_0() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(0, 0))
    res = stats.new_percent_saved(rep)
    assert res == "0.00% (0 bytes)"


def test__report_saved_verbose() -> None:
    report = "a"
    rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
    settings = Settings(None, Namespace(verbose=2))
    res = stats._report_saved(settings, rep)
    assert res == f"{PATH}: 49.51% (1004.0 bytes)\n\t{report}"


def test__report_saved_test() -> None:
    report = "a"
    rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
    settings = Settings(None, Namespace(test=True))
    res = stats._report_saved(settings, rep)
    assert res == f"{PATH}: 49.51% (1004.0 bytes) could be saved.\n\t{report}"


def test_report_saved_verbose() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
    settings = Settings(None, Namespace(verbose=2))
    stats.report_saved(settings, rep)


def test_report_saved_test() -> None:
    rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
    settings = Settings(None, Namespace(test=True))
    stats.report_saved(settings, rep)


def test_report_totals_verbose() -> None:
    settings = Settings(None, Namespace(verbose=2))
    stats.report_totals(settings, 2048, 1024, True, [])


def test_report_totals_test() -> None:
    settings = Settings(None, Namespace(test=True))
    stats.report_totals(settings, 2048, 1024, True, [])


def test_report_totals_test_zero() -> None:
    settings = Settings(None, Namespace(test=True))
    stats.report_totals(settings, 2048, 2048, True, [])


def test_report_totals_test_neg() -> None:
    settings = Settings(None, Namespace(test=True))
    stats.report_totals(settings, 1024, 2048, True, [])


def test_report_totals_zero() -> None:
    settings = Settings(None, Namespace())
    stats.report_totals(settings, 2048, 2048, True, [])


def test_report_totals_bytes_in_zero() -> None:
    settings = Settings(None, Namespace())
    stats.report_totals(settings, 0, 2048, True, [])


def test_report_totals_neg() -> None:
    settings = Settings(None, Namespace())
    stats.report_totals(settings, 1024, 2048, True, [])


def test_report_totals_zero_quiet() -> None:
    settings = Settings(None, Namespace(test=True))
    settings.verbose = 0
    stats.report_totals(settings, 2048, 2028, True, [])


def test_report_totals_errors() -> None:
    settings = Settings(None, Namespace())
    errors = [(PATH, "dummyError")]
    stats.report_totals(settings, 0, 2048, True, errors)


def test_report_noop_quiet() -> None:
    settings = Settings(None, Namespace(test=True))
    settings.verbose = 0
    stats.report_totals(settings, 0, 0, True, [])
