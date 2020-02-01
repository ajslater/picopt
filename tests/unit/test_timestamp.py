"""Test timestamp module."""
import shutil

from pathlib import Path
from typing import Tuple

from picopt import timestamp
from picopt.settings import Settings
from picopt.timestamp import Timestamp
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
DEEP_TMP = TMP_ROOT / "deep"
DEEP_TMP_FILE = TMP_ROOT / "deep/file"


def _setup(path: Path = TMP_ROOT) -> Tuple[Path, float, Timestamp]:
    _teardown()
    path.mkdir(parents=True)
    record_path = path / timestamp.RECORD_FILENAME
    record_path.touch()
    mtime = record_path.stat().st_mtime
    tso = Timestamp(Settings())
    return record_path, mtime, tso


def _setup_record() -> Tuple[Path, Timestamp]:
    _teardown()
    record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    DEEP_TMP.mkdir(parents=True)
    return record_path, Timestamp(Settings())


def _teardown() -> None:
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_get_timestamp_invalid() -> None:
    path = TMP_ROOT / "BLARGH"
    res = Timestamp(Settings())._get_timestamp(path, False)
    assert res is None


def test_get_timestamp_no_remove() -> None:
    record_path, mtime, tso = _setup()
    res = tso._get_timestamp(TMP_ROOT, False)

    assert res == mtime
    _teardown()


def test_get_timestamp_remove() -> None:
    record_path, mtime, tso = _setup()
    tso._settings.record_timestamp = True
    res = tso._get_timestamp(TMP_ROOT, True)

    assert res == mtime
    assert record_path in tso._old_timestamps
    _teardown()


def test_get_timestamp_cached() -> None:
    record_path, mtime, tso = _setup()
    assert TMP_ROOT not in tso._timestamp_cache
    res = tso._get_timestamp_cached(TMP_ROOT, False)
    assert res == mtime
    assert tso._timestamp_cache[TMP_ROOT] == mtime

    res = tso._get_timestamp_cached(TMP_ROOT, False)
    assert res == mtime
    _teardown()


def test_max_none_nums() -> None:
    res = Timestamp.max_none((1, 2))
    assert res == 2


def test_max_none_none() -> None:
    res = Timestamp.max_none((1, None))
    assert res == 1


def test_max_none_none_none() -> None:
    res = Timestamp.max_none((None, None))
    assert res is None


def test_max_timestamps_none() -> None:
    record_path, mtime, tso = _setup()
    res = tso._max_timestamps(TMP_ROOT, False, None)
    assert res == mtime
    _teardown()


def test_max_timestamps_tstamp() -> None:
    record_path, mtime, tso = _setup()
    tstamp = mtime + 100
    res = tso._max_timestamps(TMP_ROOT, False, tstamp)
    assert res == tstamp
    _teardown()


def test_get_parent_timestamp_none() -> None:
    record_path, mtime, tso = _setup()
    DEEP_TMP.mkdir()
    res = tso._get_parent_timestamp(DEEP_TMP, None)
    assert res == mtime
    _teardown()


def test_get_parent_timestamp_tstamp() -> None:
    record_path, mtime, tso = _setup()
    DEEP_TMP.mkdir()
    tstamp = mtime + 100
    res = tso._get_parent_timestamp(DEEP_TMP, tstamp)
    assert res == tstamp
    _teardown()


def test_get_walk_after_none() -> None:
    record_path, mtime, tso = _setup()
    assert record_path.exists()
    print("made:", record_path)
    res = tso.get_walk_after(TMP_ROOT, None)
    assert res == mtime


def test_get_walk_after_settings() -> None:
    record_path, mtime, tso = _setup()
    oatime = mtime + 100
    tso._settings.optimize_after = oatime
    res = tso.get_walk_after(TMP_ROOT, None)
    assert res == oatime


def test_get_walk_after_settings_tstamp() -> None:
    record_path, mtime, tso = _setup()
    tstamp = mtime + 100
    res = tso.get_walk_after(TMP_ROOT, tstamp)
    assert res == tstamp


def test_get_walk_after_settings_file() -> None:
    record_path, mtime, tso = _setup()
    tstamp = mtime + 100
    path = TMP_ROOT / "text.txt"
    path.touch()
    res = tso.get_walk_after(path, tstamp)
    assert res == tstamp


def test_should_record_timestamp_unset() -> None:
    tso = Timestamp(Settings())
    res, reason = tso._should_record_timestamp(TMP_ROOT)
    assert not res
    assert reason == timestamp._REASON_DEFAULT


def test_should_record_timestamp_set_symlink() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso._settings.follow_symlinks = False
    DEEP_TMP_FILE.symlink_to(TMP_ROOT)
    res, reason = tso._should_record_timestamp(DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_SYMLINK
    _teardown()


def test_should_record_timestamp_set_symlink_quiet() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso._settings.follow_symlinks = False
    tso._settings.verbose = 0
    DEEP_TMP_FILE.symlink_to(TMP_ROOT)
    res, reason = tso._should_record_timestamp(DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_SYMLINK
    _teardown()


def test_should_record_timestamp_set_file() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    DEEP_TMP_FILE.touch()
    res, reason = tso._should_record_timestamp(DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_NONDIR
    _teardown()


def test_should_record_timestamp_set_file_quiet() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso._settings.verbose = 0
    DEEP_TMP_FILE.touch()
    res, reason = tso._should_record_timestamp(DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_NONDIR
    _teardown()


def test_should_record_timestamp_true() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso._settings.verbose = 0
    res, reason = tso._should_record_timestamp(DEEP_TMP)
    assert res
    assert reason == timestamp._REASON_DEFAULT
    _teardown()


def test_remove_old_timestamp() -> None:
    deep_record_path, _, tso = _setup(DEEP_TMP)
    tso._settings.record_timestamp = True
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    tso._get_timestamp_cached(DEEP_TMP, True)
    removed = tso._remove_old_timestamps(TMP_ROOT, parent_record_path)
    assert not deep_record_path.exists()
    assert len(removed) == 1
    assert removed[deep_record_path] is None
    _teardown()


def test_remove_old_timestamp_skip() -> None:
    deep_record_path, _, tso = _setup(DEEP_TMP)
    tso._settings.record_timestamp = True
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    tso._get_timestamp_cached(DEEP_TMP, True)
    removed = tso._remove_old_timestamps(TMP_ROOT, deep_record_path)
    assert deep_record_path.exists()
    assert len(removed) == 0
    _teardown()


def test_remove_old_timestamp_quiet() -> None:
    deep_record_path, _, tso = _setup(DEEP_TMP)
    tso._settings.record_timestamp = True
    tso._settings.verbose = 0
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    tso._get_timestamp_cached(DEEP_TMP, True)
    removed = tso._remove_old_timestamps(TMP_ROOT, parent_record_path)
    assert not deep_record_path.exists()
    assert len(removed) == 1
    assert removed[deep_record_path] is None
    _teardown()


def test_remove_old_timestamp_error() -> None:
    deep_record_path, _, tso = _setup(DEEP_TMP)
    tso._settings.record_timestamp = True
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    tso._get_timestamp_cached(DEEP_TMP, True)
    deep_record_path.unlink()
    deep_record_path.mkdir()
    removed = tso._remove_old_timestamps(TMP_ROOT, parent_record_path)
    assert deep_record_path.exists()
    assert len(removed) == 1
    assert isinstance(removed[deep_record_path], OSError)
    _teardown()


def test_record_timestamp_set() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso.record_timestamp(DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_quiet() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    tso._settings.verbose = 0
    tso.record_timestamp(DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_not() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = False
    tso.record_timestamp(DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert not deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_not_quiet() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = False
    tso._settings.verbose = 0
    tso.record_timestamp(DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert not deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_error() -> None:
    record_path, tso = _setup_record()
    tso._settings.record_timestamp = True
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    shutil.rmtree(DEEP_TMP)
    tso.record_timestamp(DEEP_TMP)
    assert not deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_remove() -> None:
    deep_record_path, _, tso = _setup(DEEP_TMP)
    tso._settings.record_timestamp = True
    tso._get_timestamp_cached(DEEP_TMP, True)
    assert deep_record_path.exists()
    tso.record_timestamp(TMP_ROOT)
    assert not deep_record_path.exists()
    record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    assert record_path.exists()
    _teardown()
