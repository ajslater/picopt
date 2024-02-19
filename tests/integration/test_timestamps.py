"""Test comic format."""
import shutil
from datetime import datetime, timezone
from types import MappingProxyType

from ruamel.yaml import YAML

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir

__all__ = ()
TMP_ROOT = get_test_dir()
FN = "test_jpg.jpg"
SRC_JPG = IMAGES_DIR / FN
TMP_FN = str(TMP_ROOT / FN)
TIMESTAMPS_FN = f".{PROGRAM_NAME}_treestamps.yaml"
TIMESTAMPS_PATH = TMP_ROOT / TIMESTAMPS_FN
WAL_FN = f".{PROGRAM_NAME}_treestamps.wal.yaml"
WAL_PATH = TMP_ROOT / WAL_FN

FNS = MappingProxyType({FN: (97373, 87913)})

DEFAULT_CONFIG = {
    "bigger": False,
    "convert_to": [],
    "formats": ["GIF", "JPEG", "PNG", "SVG", "WEBP"],
    "keep_metadata": True,
    "ignore": [],
    "near_lossless": False,
    "recurse": True,
    "symlinks": True,
}

TREESTAMPS_CONFIG = {"ignore": [], "symlinks": True}


class TestTimestamps:
    """Test containers dir."""

    @staticmethod
    def _assert_sizes(index, root=TMP_ROOT):
        """Assert sizes."""
        for name, sizes in FNS.items():
            path = root / name
            assert path.stat().st_size == sizes[index]

    def setup_method(self) -> None:
        """Set up method."""
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, TMP_ROOT)
        self._assert_sizes(0)

    def teardown_method(self) -> None:
        """Tear down method."""
        print(sorted(TMP_ROOT.iterdir()))  # T201
        assert TIMESTAMPS_PATH.exists()
        assert not WAL_PATH.exists()
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    @staticmethod
    def _write_timestamp(path, ts=None, config=None):
        """Write timestamp."""
        if ts is None:
            ts = datetime.now(tz=timezone.utc).timestamp()
        if config is None:
            config = DEFAULT_CONFIG
        ts_config = {**TREESTAMPS_CONFIG}
        for key in TREESTAMPS_CONFIG:
            ts_config[key] = config[key]
        yaml = {"config": config, "treestamps_config": ts_config, str(path): ts}
        YAML().dump(yaml, TIMESTAMPS_PATH)
        assert TIMESTAMPS_PATH.exists()
        assert not WAL_PATH.exists()
        print(yaml)

    def test_no_timestamp(self) -> None:
        """Test no timestamp."""
        args = (PROGRAM_NAME, "-rtvvvx SVG", TMP_FN)
        cli.main(args)
        self._assert_sizes(1)

    def test_timestamp(self):
        """Test timestamp."""
        self._write_timestamp(TMP_FN)
        args = (PROGRAM_NAME, "-rtvvvx SVG", TMP_FN)
        cli.main(args)
        self._assert_sizes(0)

    def test_different_config(self):
        """Test different config."""
        self._write_timestamp(FN)
        args = (PROGRAM_NAME, "-brtvvvx SVG", TMP_FN)
        cli.main(args)
        self._assert_sizes(1)

    def test_timestamp_dir(self):
        """Test timestamp dir."""
        self._write_timestamp(TMP_ROOT)
        args = (PROGRAM_NAME, "-rtvvvx SVG", TMP_FN)
        cli.main(args)
        self._assert_sizes(0)

    def _setup_child_dir(self):
        """Set up child dir."""
        tmp_child_dir = TMP_ROOT / "child"
        tmp_child_dir.mkdir(exist_ok=True)
        shutil.move(TMP_ROOT / FN, tmp_child_dir)
        self._assert_sizes(0, tmp_child_dir)
        return tmp_child_dir

    def test_timestamp_children(self):
        """Test timestamp children."""
        tmp_child_dir = self._setup_child_dir()
        self._write_timestamp(tmp_child_dir)
        args = (PROGRAM_NAME, "-rtvvvx SVG", str(TMP_ROOT))
        cli.main(args)
        self._assert_sizes(0, tmp_child_dir)

    def test_timestamp_parents(self):
        """Test timestamp parents."""
        tmp_child_dir = self._setup_child_dir()

        self._write_timestamp(TMP_ROOT)
        args = (PROGRAM_NAME, "-rtvvvx SVG", str(tmp_child_dir))
        cli.main(args)
        self._assert_sizes(0, tmp_child_dir)
        assert (tmp_child_dir / TIMESTAMPS_FN).exists()
        assert not (tmp_child_dir / WAL_FN).exists()

    def test_journal_cleanup(self) -> None:
        """Test journal cleanup."""
        args = (PROGRAM_NAME, "-rtvvvx SVG", TMP_FN)
        cli.main(args)
        assert not WAL_PATH.exists()

    @staticmethod
    def _write_wal(path, ts=None, config=None):
        """Write wal."""
        if ts is None:
            ts = datetime.now(tz=timezone.utc).timestamp()
        if config is None:
            config = DEFAULT_CONFIG
        ts_config = {**TREESTAMPS_CONFIG}
        for key in TREESTAMPS_CONFIG:
            ts_config[key] = config[key]
        yaml = {
            "config": config,
            "treestamps_config": ts_config,
            "wal": [{str(path): ts}],
        }
        YAML().dump(yaml, WAL_PATH)

    def test_timestamp_read_journal(self):
        """Test timestamp read journal."""
        self._write_wal(TMP_FN)
        args = (PROGRAM_NAME, "-rtvvvx SVG", TMP_FN)
        cli.main(args)
        self._assert_sizes(0)
