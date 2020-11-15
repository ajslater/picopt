"""Test timestamp module."""
import shutil

from argparse import Namespace
from datetime import datetime
from pathlib import Path
from sys import platform

from ruamel.yaml import YAML

from picopt.settings import Settings
from picopt.timestamp import OLD_TIMESTAMP_FN
from picopt.timestamp import TIMESTAMPS_FN
from picopt.timestamp import Timestamp
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
DEEP_PATH = TMP_ROOT / "deep"
TIMESTAMP_PATH = TMP_ROOT / TIMESTAMPS_FN
DEEP_TIMESTAMP_PATH = DEEP_PATH / TIMESTAMPS_FN
MTIME = datetime.now().timestamp()
TIMESTAMPS = {str(TMP_ROOT): MTIME}
PATH_TIMESTAMPS = {TMP_ROOT: MTIME}
DEEP_MTIME = datetime.now().timestamp()
DEEP_TIMESTAMPS = {str(DEEP_PATH): DEEP_MTIME}
SETTINGS = Settings(arg_namespace=Namespace(timestamps_path=TIMESTAMP_PATH))


class TestTimestampStatic:
    def test_parse_date_string(self) -> None:
        res = Timestamp.parse_date_string("2020-Jan-10 10:25:03pm")
        if platform == "darwin":
            assert res == 1578723903.0
        elif platform == "linux":
            assert res == 1578695103.0


class TestTimestamp:

    path = TMP_ROOT
    deep = DEEP_PATH
    old_timestamp_path = path / OLD_TIMESTAMP_FN
    yaml = YAML()

    def setup_method(self) -> None:
        self.deep.mkdir(parents=True)
        self.yaml.dump(TIMESTAMPS, TIMESTAMP_PATH)
        self.tso = Timestamp(SETTINGS, TMP_ROOT)

    def teardown_method(self) -> None:
        shutil.rmtree(self.path)

    def _setup_old_timestamp(self) -> None:
        self.old_timestamp_path.touch()
        self.old_mtime = self.old_timestamp_path.stat().st_mtime
        assert self.old_timestamp_path.exists()

    def test_init_dump_file(self) -> None:
        self.tso = Timestamp(SETTINGS, TIMESTAMP_PATH)
        assert self.tso._dump_path == TIMESTAMP_PATH

    def test_get_timestamp_invalid(self) -> None:
        path = TMP_ROOT / "BLARGH"
        res = self.tso._get_timestamp(path)
        assert res == MTIME

    def test_get_old_timestamp(self) -> None:
        self._setup_old_timestamp()
        res = self.tso.upgrade_old_timestamp(self.old_timestamp_path)

        assert res == self.old_mtime
        assert not self.old_timestamp_path.exists()

    def test_get_timestamp(self) -> None:
        res = self.tso._get_timestamp(TMP_ROOT)
        assert res == MTIME

    def test_upgrade_old_timestamp(self) -> None:
        self._setup_old_timestamp()
        self.tso.upgrade_old_timestamp(self.old_timestamp_path)
        res = self.tso._get_timestamp(TMP_ROOT)
        assert res == self.old_mtime
        assert not self.old_timestamp_path.exists()

    def test_upgrade_old_parent_timestamps(self) -> None:
        self._setup_old_timestamp()
        assert self.old_timestamp_path.exists()
        mtime = self.tso.upgrade_old_parent_timestamps(self.deep)
        res = self.tso._get_timestamp(self.deep)
        assert res == mtime
        assert not self.old_timestamp_path.exists()

    def test_compact_timestamps(self) -> None:
        bar_path = self.deep / "bar.txt"
        file_path = self.path / "file.txt"
        foo_path = self.deep / "foo.txt"
        foo_path.touch()
        bar_path.touch()
        file_path.touch()
        self.tso.record_timestamp(foo_path)
        mtime = self.tso.record_timestamp(bar_path)
        file_mtime = self.tso.record_timestamp(file_path)
        self.tso.compact_timestamps(self.deep)
        timestamps = self.tso._load_timestamps(TMP_ROOT)
        compare_dict = {self.path: MTIME, self.deep: mtime, file_path: file_mtime}
        assert timestamps == compare_dict

    def test_max_none_nums(self) -> None:
        res = Timestamp.max_none((1, 2))
        assert res == 2

    def test_max_none_none(self) -> None:
        res = Timestamp.max_none((1, None))
        assert res == 1

    def test_max_none_none_none(self) -> None:
        res = Timestamp.max_none((None, None))
        assert res is None

    def test_max_timestamps_none(self) -> None:
        res = self.tso._max_timestamps(TMP_ROOT, None)
        assert res == MTIME

    def test_max_timestamps_tstamp(self) -> None:
        tstamp = MTIME + 100
        res = self.tso._max_timestamps(TMP_ROOT, tstamp)
        assert res == tstamp

    def test_get_timestamp_recursive_up_none(self) -> None:
        res = self.tso._get_timestamp_recursive_up(self.deep, None)
        assert res == MTIME

    def test_get_timestamp_recursive_up_tstamp(self) -> None:
        tstamp = MTIME + 100
        res = self.tso._get_timestamp_recursive_up(self.deep, tstamp)
        assert res == tstamp

    def test_get_walk_after_none(self) -> None:
        res = self.tso.get_walk_after(TMP_ROOT, None)
        assert res == MTIME

    def test_get_walk_after_settings(self) -> None:
        oatime = MTIME + 100
        self.tso._settings.optimize_after = oatime
        res = self.tso.get_walk_after(TMP_ROOT, None)
        assert res == oatime

    def test_get_walk_after_settings_tstamp(self) -> None:
        tstamp = MTIME + 100
        res = self.tso.get_walk_after(TMP_ROOT, tstamp)
        assert res == tstamp

    def test_get_walk_after_file(self) -> None:
        tstamp = MTIME + 100
        path = self.path / "text.txt"
        path.touch()
        res = self.tso.get_walk_after(path, tstamp)
        assert res == tstamp

    def test_should_record_timestamp(self) -> None:
        res = self.tso._should_record_timestamp(TMP_ROOT)
        assert res

    def test_should_record_timestamp_symlink(self) -> None:
        self.tso._settings.follow_symlinks = False
        sym_path = self.path / "sym"
        sym_path.symlink_to(self.deep)
        res = self.tso._should_record_timestamp(sym_path)
        assert not res

    def test_should_record_timestamp_dne(self) -> None:
        self.tso._settings.follow_symlinks = False
        bad_path = self.path / "BLARGS"
        res = self.tso._should_record_timestamp(bad_path)
        assert not res

    def test_should_record_timestamp_test(self) -> None:
        self.tso._settings.test = True
        res = self.tso._should_record_timestamp(TMP_ROOT)
        assert not res

    def test_record_timestamp(self) -> None:
        res = self.tso.record_timestamp(TMP_ROOT / "blarg")
        assert res is None

    def test__load_one_timestamp_file(self) -> None:
        timestamps = self.tso._load_one_timestamps_file(TIMESTAMP_PATH)
        assert timestamps == PATH_TIMESTAMPS

    def test__load_one_timestamp_file_not_a_file(self) -> None:
        timestamps = self.tso._load_one_timestamps_file(TMP_ROOT)
        assert timestamps is None

    def test__load_one_timestamp_empty(self) -> None:
        with open(TIMESTAMP_PATH, "w") as tf:
            tf.write("")
        timestamps = self.tso._load_one_timestamps_file(TIMESTAMP_PATH)
        assert timestamps == {}

    def test__load_one_timestamp_bad(self) -> None:
        with open(TIMESTAMP_PATH, "w") as tf:
            tf.write("nok: blarg")
        timestamps = self.tso._load_one_timestamps_file(TIMESTAMP_PATH)
        assert timestamps == {}

    def test__load_one_timestamp_os_error(self) -> None:
        timestamps = self.tso._load_one_timestamps_file(Path("/dev/stderr"))
        assert timestamps == {}

    def test__load_timestamps(self) -> None:
        timestamps = self.tso._load_timestamps(DEEP_TIMESTAMP_PATH)
        assert timestamps == PATH_TIMESTAMPS

    def test__load_timestamps_none(self) -> None:
        TIMESTAMP_PATH.unlink()
        timestamps = self.tso._load_timestamps(DEEP_TIMESTAMP_PATH)
        assert timestamps == {}

    def test__load_timestamps_none_quiet(self) -> None:
        TIMESTAMP_PATH.unlink()
        self.tso._settings.verbose = 0
        timestamps = self.tso._load_timestamps(DEEP_TIMESTAMP_PATH)
        assert timestamps == {}

    def test__serialize_timestamps(self) -> None:
        dumpable_timestamps = self.tso._serialize_timestamps()
        assert dumpable_timestamps == TIMESTAMPS

    def test__serialize_timestamps_none(self) -> None:
        self.tso._timestamps[TMP_ROOT] = None
        dumpable_timestamps = self.tso._serialize_timestamps()
        assert dumpable_timestamps == {}

    def test_consume_child_timestamp_newer(self) -> None:
        self.yaml.dump(DEEP_TIMESTAMPS, DEEP_TIMESTAMP_PATH)
        self.tso.consume_child_timestamps(DEEP_TIMESTAMP_PATH)
        assert self.tso._timestamps[TMP_ROOT] == MTIME
        assert self.tso._timestamps[DEEP_PATH] == DEEP_MTIME
        assert not DEEP_TIMESTAMP_PATH.exists()

    def test_consume_child_timestamp_same(self) -> None:
        self.yaml.dump(TIMESTAMPS, DEEP_TIMESTAMP_PATH)
        self.tso.consume_child_timestamps(DEEP_TIMESTAMP_PATH)
        assert self.tso._timestamps[TMP_ROOT] == MTIME
        assert self.tso._timestamps.get(DEEP_PATH) is None
        assert not DEEP_TIMESTAMP_PATH.exists()

    def test_consume_child_timestamp_irrelevant(self) -> None:
        self.yaml.dump({"/tmp": 0}, DEEP_TIMESTAMP_PATH)
        self.tso.consume_child_timestamps(DEEP_TIMESTAMP_PATH)
        assert self.tso._timestamps[TMP_ROOT] == MTIME
        assert self.tso._timestamps.get(DEEP_PATH) is None
        assert not DEEP_TIMESTAMP_PATH.exists()
