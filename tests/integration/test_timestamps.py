"""Test comic format."""
import platform
import shutil

from datetime import datetime

from ruamel.yaml import YAML

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
FN = "test_jpg.jpg"
SRC_JPG = IMAGES_DIR / FN
TMP_FN = str(TMP_ROOT / FN)
TIMESTAMPS_FN = ".picopt_treestamps.yaml"
TIMESTAMPS_PATH = TMP_ROOT / TIMESTAMPS_FN
WAL_FN = ".picopt_treestamps.wal.yaml"
WAL_PATH = TMP_ROOT / WAL_FN

if platform.system() == "Darwin":
    FNS = {
        FN: (97373, 87913),
    }
else:
    FNS = {
        FN: (97373, 87922),
    }

DEFAULT_CONFIG = {
    "bigger": False,
    "convert_to": [],
    "formats": ["GIF", "PNG", "JPEG", "WEBP"],
    "keep_metadata": True,
    "ignore": [],
    "recurse": True,
    "symlinks": True,
}


class TestContainersDir:
    @staticmethod
    def _assert_sizes(index, root=TMP_ROOT):
        for name, sizes in FNS.items():
            path = root / name
            assert path.stat().st_size == sizes[index]

    def setup_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)
        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, TMP_ROOT)
        self._assert_sizes(0)

    def teardown_method(self) -> None:
        print(sorted(TMP_ROOT.iterdir()))
        assert TIMESTAMPS_PATH.exists()
        assert not WAL_PATH.exists()
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    @staticmethod
    def _write_timestamp(path, ts=None, config=None):
        if ts is None:
            ts = datetime.now().timestamp()
        if config is None:
            config = DEFAULT_CONFIG
        yaml = {"config": config, str(path): ts}
        YAML().dump(yaml, TIMESTAMPS_PATH)
        assert TIMESTAMPS_PATH.exists()
        assert not WAL_PATH.exists()

    def test_no_timestamp(self) -> None:
        args = (PROGRAM_NAME, "-rtvv", TMP_FN)
        res = cli.main(args)
        assert res
        self._assert_sizes(1)

    def test_timestamp(self):
        self._write_timestamp(FN)
        args = (PROGRAM_NAME, "-rtvv", TMP_FN)
        res = cli.main(args)
        assert res
        self._assert_sizes(0)

    def test_different_config(self):
        self._write_timestamp(FN)
        args = (PROGRAM_NAME, "-brtvv", TMP_FN)
        res = cli.main(args)
        assert res
        self._assert_sizes(1)

    def test_timestamp_dir(self):
        self._write_timestamp(TMP_ROOT)
        args = (PROGRAM_NAME, "-rtvv", TMP_FN)
        res = cli.main(args)
        assert res
        self._assert_sizes(0)

    def _setup_child_dir(self):
        tmp_child_dir = TMP_ROOT / "child"
        tmp_child_dir.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, tmp_child_dir)
        self._assert_sizes(0, tmp_child_dir)
        return tmp_child_dir

    def test_timestamp_children(self):
        tmp_child_dir = self._setup_child_dir()
        self._write_timestamp(tmp_child_dir)
        args = (PROGRAM_NAME, "-rtvv", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        self._assert_sizes(1)
        self._assert_sizes(0, tmp_child_dir)

    def test_timestamp_parents(self):
        tmp_child_dir = self._setup_child_dir()

        self._write_timestamp(TMP_ROOT)
        args = (PROGRAM_NAME, "-rtvv", str(tmp_child_dir))
        res = cli.main(args)
        assert res
        self._assert_sizes(0, tmp_child_dir)
        assert (tmp_child_dir / TIMESTAMPS_FN).exists()
        assert not (tmp_child_dir / WAL_FN).exists()

    def test_journal_cleanup(self) -> None:
        args = (PROGRAM_NAME, "-rtvv", TMP_FN)
        res = cli.main(args)
        assert res
        assert not WAL_PATH.exists()

    @staticmethod
    def _write_wal(path, ts=None, config=None):
        if ts is None:
            ts = datetime.now().timestamp()
        if config is None:
            config = DEFAULT_CONFIG
        yaml = {"config": config, "wal": [{str(path): ts}]}
        YAML().dump(yaml, WAL_PATH)

    def test_timestamp_read_journal(self):
        self._write_wal(TMP_FN)
        args = (PROGRAM_NAME, "-rtvv", TMP_FN)
        res = cli.main(args)
        assert res
        self._assert_sizes(0)
