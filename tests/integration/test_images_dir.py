"""Test comic format."""
import shutil

from picopt import PROGRAM_NAME
from picopt import cli
from tests import IMAGES_DIR
from tests import get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
ARGS = (PROGRAM_NAME, "--config", str(TMP_ROOT))


class TestImagesDir:
    def setup_method(self) -> None:
        shutil.copytree(IMAGES_DIR, TMP_ROOT)

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_walk_images(self) -> None:
        args = ARGS + tuple(map(str, TMP_ROOT.glob("*")))
        print(f"{args=}")
        res = cli.run(args)
        assert res

    def test_all_once(self) -> None:
        args = ARGS + ("-rct", str(TMP_ROOT))
        print(f"{args=}")
        res = cli.run(args)
        assert res
