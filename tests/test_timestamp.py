"""Test timestamp module."""
import fcntl
import shutil

from pathlib import Path
from typing import Tuple

from picopt import timestamp
from picopt.settings import Settings


__all__ = ()
TMP_ROOT = Path("/tmp/picopt-timestamp")
DEEP_TMP = TMP_ROOT / "deep"
DEEP_TMP_FILE = TMP_ROOT / "deep/file"
TEST_FILES_ROOT = Path("tests/test_files")


def _setup(path: Path = TMP_ROOT) -> Tuple[Path, float, Settings]:
    _teardown()
    path.mkdir(parents=True)
    record_path = path / timestamp.RECORD_FILENAME
    record_path.touch()
    return record_path, record_path.stat().st_mtime, Settings()


def _setup_record() -> Tuple[Path, Settings]:
    _teardown()
    record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    DEEP_TMP.mkdir(parents=True)
    return record_path, Settings()


def _teardown():
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)


def test_get_timestamp_invalid() -> None:
    path = TMP_ROOT / "BLARGH"
    res = timestamp._get_timestamp(Settings(), path, False)
    assert res is None


def test_get_timestamp_no_remove() -> None:
    record_path, mtime, settings = _setup()
    res = timestamp._get_timestamp(settings, TMP_ROOT, False)

    assert res == mtime
    _teardown()


def test_get_timestamp_remove() -> None:
    record_path, mtime, settings = _setup()
    settings.record_timestamp = True
    res = timestamp._get_timestamp(settings, TMP_ROOT, True)

    assert res == mtime
    assert record_path in timestamp.OLD_TIMESTAMPS
    _teardown()


def test_get_timestamp_cached():
    record_path, mtime, settings = _setup()
    assert TMP_ROOT not in timestamp.TIMESTAMP_CACHE
    res = timestamp._get_timestamp_cached(settings, TMP_ROOT, False)
    assert res == mtime
    assert timestamp.TIMESTAMP_CACHE[TMP_ROOT] == mtime

    res = timestamp._get_timestamp_cached(settings, TMP_ROOT, False)
    assert res == mtime
    _teardown()


def test_max_none_nums():
    res = timestamp.max_none((1, 2))
    assert res == 2


def test_max_none_none():
    res = timestamp.max_none((1, None))
    assert res == 1


def test_max_none_none_none():
    res = timestamp.max_none((None, None))
    assert res is None


def test_max_timestamps_none():
    record_path, mtime, settings = _setup()
    res = timestamp._max_timestamps(settings, TMP_ROOT, False, None)
    assert res == mtime
    _teardown()


def test_max_timestamps_tstamp():
    record_path, mtime, settings = _setup()
    tstamp = mtime + 100
    res = timestamp._max_timestamps(settings, TMP_ROOT, False, tstamp)
    assert res == tstamp
    _teardown()


def test_get_parent_timestamp_none():
    record_path, mtime, settings = _setup()
    DEEP_TMP.mkdir()
    res = timestamp._get_parent_timestamp(settings, DEEP_TMP, None)
    assert res == mtime
    _teardown()


def test_get_parent_timestamp_tstamp():
    record_path, mtime, settings = _setup()
    DEEP_TMP.mkdir()
    tstamp = mtime + 100
    res = timestamp._get_parent_timestamp(settings, DEEP_TMP, tstamp)
    assert res == tstamp
    _teardown()


def test_get_walk_after_none():
    record_path, mtime, settings = _setup()
    res = timestamp.get_walk_after(settings, TMP_ROOT, None)
    assert res == mtime


def test_get_walk_after_settings():
    record_path, mtime, settings = _setup()
    settings.optimize_after = mtime + 100
    res = timestamp.get_walk_after(settings, TMP_ROOT, None)
    assert res == mtime


def test_get_walk_after_settings_tstamp():
    record_path, mtime, settings = _setup()
    tstamp = mtime + 100
    res = timestamp.get_walk_after(settings, TMP_ROOT, tstamp)
    assert res == tstamp


def test_should_record_timestamp_unset():
    settings = Settings()
    res, reason = timestamp._should_record_timestamp(settings, TMP_ROOT)
    assert not res
    assert reason == timestamp._REASON_DEFAULT


def test_should_record_timestamp_set_symlink():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    settings.follow_symlinks = False
    DEEP_TMP_FILE.symlink_to(TMP_ROOT)
    res, reason = timestamp._should_record_timestamp(settings, DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_SYMLINK
    _teardown()


def test_should_record_timestamp_set_symlink_quiet():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    settings.follow_symlinks = False
    settings.verbose = 0
    DEEP_TMP_FILE.symlink_to(TMP_ROOT)
    res, reason = timestamp._should_record_timestamp(settings, DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_SYMLINK
    _teardown()


def test_should_record_timestamp_set_file():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    DEEP_TMP_FILE.touch()
    res, reason = timestamp._should_record_timestamp(settings, DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_NONDIR
    _teardown()


def test_should_record_timestamp_set_file_quiet():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    settings.verbose = 0
    DEEP_TMP_FILE.touch()
    res, reason = timestamp._should_record_timestamp(settings, DEEP_TMP_FILE)
    assert not res
    assert reason == timestamp._REASON_NONDIR
    _teardown()


def test_should_record_timestamp_true():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    settings.verbose = 0
    res, reason = timestamp._should_record_timestamp(settings, DEEP_TMP)
    assert res
    assert reason == timestamp._REASON_DEFAULT
    _teardown()


def test_remove_old_timestamp():
    deep_record_path, _, settings = _setup(DEEP_TMP)
    settings.record_timestamp = True
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    timestamp._get_timestamp_cached(settings, DEEP_TMP, True)
    removed = timestamp._remove_old_timestamps(settings, TMP_ROOT, parent_record_path)
    assert not deep_record_path.exists()
    assert len(removed) == 1
    assert removed[deep_record_path] is None
    _teardown()


def test_remove_old_timestamp_quiet():
    deep_record_path, _, settings = _setup(DEEP_TMP)
    settings.record_timestamp = True
    settings.verbose = 0
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    timestamp._get_timestamp_cached(settings, DEEP_TMP, True)
    removed = timestamp._remove_old_timestamps(settings, TMP_ROOT, parent_record_path)
    assert not deep_record_path.exists()
    assert len(removed) == 1
    assert removed[deep_record_path] is None
    _teardown()


def test_remove_old_timestamp_error():
    deep_record_path, _, settings = _setup(DEEP_TMP)
    settings.record_timestamp = True
    parent_record_path = TMP_ROOT / timestamp.RECORD_FILENAME
    parent_record_path.touch()
    timestamp._get_timestamp_cached(settings, DEEP_TMP, True)
    deep_record_path.unlink()
    deep_record_path.mkdir()
    removed = timestamp._remove_old_timestamps(settings, TMP_ROOT, parent_record_path)
    assert deep_record_path.exists()
    assert len(removed) == 1
    assert isinstance(removed[deep_record_path], OSError)
    _teardown()


def test_record_timestamp_set():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    timestamp.record_timestamp(settings, DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_quiet():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    settings.verbose = 0
    timestamp.record_timestamp(settings, DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_not():
    record_path, settings = _setup_record()
    settings.record_timestamp = False
    timestamp.record_timestamp(settings, DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert not deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_not_quiet():
    record_path, settings = _setup_record()
    settings.record_timestamp = False
    settings.verbose = 0
    timestamp.record_timestamp(settings, DEEP_TMP)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert not deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_error():
    record_path, settings = _setup_record()
    settings.record_timestamp = True
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    with open(deep_record_path, "w+") as record_file:
        fcntl.flock(record_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        timestamp.record_timestamp(settings, DEEP_TMP)
        fcntl.flock(record_file, fcntl.LOCK_UN)
    assert deep_record_path.exists()
    _teardown()


def test_record_timestamp_set_remove():
    record_path, settings = _setup_record()
    settings.record_timestamp = True

    timestamp.record_timestamp(settings, DEEP_TMP)
    timestamp.record_timestamp(settings, TMP_ROOT)
    deep_record_path = DEEP_TMP / timestamp.RECORD_FILENAME
    assert not deep_record_path.exists()
    _teardown()
