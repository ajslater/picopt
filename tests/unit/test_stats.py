"""Test stats module."""
from pathlib import Path

from picopt import stats
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring

TYPE_NAME = "png"
PATH = Path("dummyPath")


class TestStats:
    def test_skip(self) -> None:
        res = stats.skip(TYPE_NAME, PATH)
        assert res.final_path == PATH
        assert res.report_list == [f"Skipping {TYPE_NAME} file: {PATH}"]
        assert res.error is None

    def test_humanize_bytes_none(self) -> None:
        hum = stats._humanize_bytes(0)
        assert hum == "no bytes"

    def test_humanize_bytes_1(self) -> None:
        hum = stats._humanize_bytes(1)
        assert hum == "1 byte"

    def test_humanize_bytes_1kb(self) -> None:
        hum = stats._humanize_bytes(1 << int(10))
        assert hum == "1 kiB"

    def test_humanize_bytes_10kb(self) -> None:
        hum = stats._humanize_bytes(10240)
        assert hum == "10.0 kiB"

    def test_humanize_bytes_huge(self) -> None:
        hum = stats._humanize_bytes(1 << int(60))
        assert hum == "1024.0 PiB"

    def test_humanize_bytes_neg(self) -> None:
        hum = stats._humanize_bytes(-10240)
        assert hum == "-10.0 kiB"

    def test_new_percent_saved_50(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(2048, 1024))
        res = stats.new_percent_saved(rep)
        assert res == "50.00% (1 kiB)"

    def test_new_percent_saved_0(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(0, 0))
        res = stats.new_percent_saved(rep)
        assert res == "0.00% (0 bytes)"


class TestStatsReport:
    def setup_method(self):
        self.settings = Settings()

    def test_report_saved_quiet(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.settings.verbose = 0
        stats.report_saved(self.settings, rep)

    def test__report_saved_verbose(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.settings.verbose = 2
        res = stats._report_saved(self.settings, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes)\n\t{report}"

    def test__report_saved_verbose_no_tools(self) -> None:
        report = ""
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.settings.verbose = 2
        res = stats._report_saved(self.settings, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes)"

    def test__report_saved_test(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.settings.test = True
        res = stats._report_saved(self.settings, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes) could be saved."

    def test_report_saved_verbose(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
        self.settings.verbose = 2
        stats.report_saved(self.settings, rep)

    def test_report_saved_test(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
        self.settings.test = True
        stats.report_saved(self.settings, rep)

    def test_report_totals_verbose(self) -> None:
        self.settings.verbose = 2
        stats.report_totals(self.settings, 2048, 1024, [])

    def test_report_totals_test(self) -> None:
        self.settings.test = True
        stats.report_totals(self.settings, 2048, 1024, [])

    def test_report_totals_test_zero(self) -> None:
        self.settings.test = True
        stats.report_totals(self.settings, 2048, 2048, [])

    def test_report_totals_test_neg(self) -> None:
        self.settings.test = True
        stats.report_totals(self.settings, 1024, 2048, [])

    def test_report_totals_zero(self) -> None:
        stats.report_totals(self.settings, 2048, 2048, [])

    def test_report_totals_bytes_in_zero(self) -> None:
        stats.report_totals(self.settings, 0, 2048, [])

    def test_report_totals_neg(self) -> None:
        stats.report_totals(self.settings, 1024, 2048, [])

    def test_report_totals_zero_quiet(self) -> None:
        self.settings.verbose = 0
        self.settings.test = True
        stats.report_totals(self.settings, 2048, 2028, [])

    def test_report_totals_errors(self) -> None:
        errors = [(PATH, "dummyError")]
        stats.report_totals(self.settings, 0, 2048, errors)

    def test_report_noop_quiet(self) -> None:
        self.settings.verbose = 0
        self.settings.test = True
        stats.report_totals(self.settings, 0, 0, [])
