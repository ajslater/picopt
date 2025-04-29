"""Test comic format."""

from types import MappingProxyType
from zipfile import ZipFile

import pytest

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, get_test_dir
from tests.integration.base import BaseTest

__all__ = ()
TMP_ROOT = get_test_dir()
SRC_CBZ = CONTAINER_DIR / "test_cbz.cbz"

FNS = MappingProxyType(
    {
        # filename       orig   no-convert     convert
        "test_delete_stored.zip": (231327, 230890, ("zip", 230890)),
        "test_cbz.cbz": (93408, 84544, ("cbz", 84544)),
        "test_cbr.cbr": (93725, 93725, ("cbz", 88035)),
        "test_rar.rar": (93675, 93675, ("zip", 88035)),
        "test_zip.zip": (7783, 7015, ("zip", 7015)),
        "igp-twss.epub": (292448, 285999, ("epub", 285999)),
        "test_7z.7z": (7613, 6836, ("zip", 6996)),
        "test_cb7.cb7": (7613, 6836, ("cbz", 6996)),
        "test_tar.tar": (11264, 10240, ("zip", 6996)),
        "test_tgz.tar.gz": (7620, 6878, ("zip", 6996)),
        "test_tbz.tar.bz2": (8071, 7332, ("zip", 6996)),
        "test_txz.tar.xz": (7612, 6908, ("zip", 6996)),
        "test_cbt.cbt": (7612, 7612, ("cbz", 6996)),
    }
)

EPUB_FN = "igp-twss.epub"
BMP_FN = "OPS/test_bmp.bmp"
NOOP_ARGS = (PROGRAM_NAME, str(TMP_ROOT))
ARGS = (
    PROGRAM_NAME,
    "-vvtx",
    "GIF,ZIP,CBZ,EPUB,RAR,CBR,7Z,CB7,TAR,TGZ,TBZ,TXZ,CBT",
)
NO_CONVERT_ARGS = (
    *ARGS,
    "-c WEBP",
    str(TMP_ROOT),
)
CONVERT_TO_ZIP_ARGS = (
    *ARGS,
    "-c",
    "ZIP,CBZ",
    str(TMP_ROOT),
)


@pytest.mark.parametrize("fn", FNS)
class TestContainersDir(BaseTest):
    """Test containers dirs."""

    TMP_ROOT = TMP_ROOT
    SOURCE_DIR = CONTAINER_DIR
    FNS = FNS

    def test_containers_noop(self, fn: str) -> None:
        """Test containers noop."""
        path = TMP_ROOT / fn
        args = (*NOOP_ARGS, str(path))
        cli.main(args)
        if fn == EPUB_FN:
            with ZipFile(path, "r") as zf:
                namelist = zf.namelist()
            assert BMP_FN in namelist
        sizes = FNS[fn]
        assert path.stat().st_size == sizes[0]

    @staticmethod
    def _vary_byte_assert(path_size, size, variation):
        # lzma & bz2 vary output size :o
        cond = abs(path_size - size) <= variation
        if not cond:
            print(f"{path_size=} != {size=}")
        assert cond

    def test_containers_no_convert(self, fn: str) -> None:
        """Test containers no convert."""
        path = TMP_ROOT / fn
        args = (*NO_CONVERT_ARGS, str(path))
        cli.main(args)
        if fn == EPUB_FN:
            with ZipFile(path, "r") as zf:
                namelist = zf.namelist()
            assert BMP_FN in namelist
        size = FNS[fn][1]
        path_size = path.stat().st_size
        if fn.endswith(("7z", "cb7", "xz", "gz")):
            self._vary_byte_assert(path_size, size, 20)
        elif fn.endswith(("bz2",)):
            self._vary_byte_assert(path_size, size, 50)
        else:
            assert path_size == size

    def test_containers_convert_to_zip(self, fn: str) -> None:
        """Test containers convert to zip."""
        sizes = FNS[fn]
        path = TMP_ROOT / fn
        args = (*CONVERT_TO_ZIP_ARGS, str(path))
        cli.main(args)
        suffix = path.suffix
        while suffix:
            # strip tar suffixes
            path = path.with_suffix("")
            suffix = path.suffix
        convert_path = path.with_suffix("." + sizes[2][0])
        assert convert_path.stat().st_size == sizes[2][1]
