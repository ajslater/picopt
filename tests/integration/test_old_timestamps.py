"""Test comic format."""
import shutil

from picopt import PROGRAM_NAME, cli
from picopt.old_timestamps import _OLD_TIMESTAMPS_NAME
from tests import IMAGES_DIR, get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
FN = "test_jpg.jpg"
SRC_JPG = IMAGES_DIR / FN
TMP_FN = str(TMP_ROOT / FN)
FNS = {
    FN: (97373, 87913),
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
        self.teardown_method()
        TMP_ROOT.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, TMP_ROOT)
        self._assert_sizes(0)

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_old_timestamp_same_dir(self) -> None:
        old_ts_path = TMP_ROOT / _OLD_TIMESTAMPS_NAME
        old_ts_path.touch()
        args = (PROGRAM_NAME, "-rtvv", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        assert not old_ts_path.exists()
        self._assert_sizes(0)

    def test_old_timestamp_child(self) -> None:
        child_root = TMP_ROOT / "child"
        child_root.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, child_root)
        old_ts_path = child_root / _OLD_TIMESTAMPS_NAME
        old_ts_path.touch()
        args = (PROGRAM_NAME, "-rtvv", str(child_root))
        res = cli.main(args)
        assert res
        assert not old_ts_path.exists()
        self._assert_sizes(0)

    def test_old_timestamp_parent(self) -> None:
        child_root = TMP_ROOT / "child"
        child_root.mkdir(exist_ok=True)
        shutil.copy(SRC_JPG, child_root)
        old_ts_path = TMP_ROOT / _OLD_TIMESTAMPS_NAME
        old_ts_path.touch()
        args = (PROGRAM_NAME, "-rtvv", str(child_root))
        res = cli.main(args)
        assert res
        assert old_ts_path.exists()
        self._assert_sizes(0)
