"""Test stats module."""
from pathlib import Path

from confuse.templates import AttrDict

from picopt import stats


__all__ = ()  # hides module from pydocstring

TYPE_NAME = "png"
PATH = Path("dummyPath")


class TestStats:
    def test_skip(self) -> None:
        res = stats.skip(PATH)
        assert res.final_path == PATH
        assert res.report_list == [f"Skipping {TYPE_NAME} file: {PATH}"]
        assert res.error is None


class TestStatsReport:
    def setup_method(self):
        self.config = AttrDict()

    def test_report_saved_quiet(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.config.verbose = 0
        stats.report_saved(self.config, rep)

    def test__report_saved_verbose(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.config.verbose = 2
        res = stats._report_saved(self.config, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes)\n\t{report}"

    def test__report_saved_verbose_no_tools(self) -> None:
        report = ""
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.config.verbose = 2
        res = stats._report_saved(self.config, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes)"

    def test__report_saved_test(self) -> None:
        report = "a"
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report=report)
        self.config.test = True
        res = stats._report_saved(self.config, rep)
        assert res == f"{PATH}: 49.51% (1004.0 bytes) could be saved."

    def test_report_saved_verbose(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
        self.config.verbose = 2
        stats.report_saved(self.config, rep)

    def test_report_saved_test(self) -> None:
        rep = stats.ReportStats(PATH, bytes_count=(2028, 1024), report="a")
        self.config.test = True
        stats.report_saved(self.config, rep)

    def test_report_totals_verbose(self) -> None:
        self.config.verbose = 2
        stats.report_totals(self.config, 2048, 1024, [])

    def test_report_totals_test(self) -> None:
        self.config.test = True
        stats.report_totals(self.config, 2048, 1024, [])

    def test_report_totals_test_zero(self) -> None:
        self.config.test = True
        stats.report_totals(self.config, 2048, 2048, [])

    def test_report_totals_test_neg(self) -> None:
        self.config.test = True
        stats.report_totals(self.config, 1024, 2048, [])

    def test_report_totals_zero(self) -> None:
        stats.report_totals(self.config, 2048, 2048, [])

    def test_report_totals_bytes_in_zero(self) -> None:
        stats.report_totals(self.config, 0, 2048, [])

    def test_report_totals_neg(self) -> None:
        stats.report_totals(self.config, 1024, 2048, [])

    def test_report_totals_zero_quiet(self) -> None:
        self.config.verbose = 0
        self.config.test = True
        stats.report_totals(self.config, 2048, 2028, [])

    def test_report_totals_errors(self) -> None:
        errors = [(PATH, "dummyError")]
        stats.report_totals(self.config, 0, 2048, errors)

    def test_report_noop_quiet(self) -> None:
        self.config.verbose = 0
        self.config.test = True
        stats.report_totals(self.config, 0, 0, [])
