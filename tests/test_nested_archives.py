"""Test optimizing archives nested inside other archives."""

import shutil
from collections.abc import Iterator
from io import BytesIO
from tarfile import TarFile
from zipfile import ZIP_STORED, ZipFile

import pytest

from picopt import PROGRAM_NAME, cli
from tests import CONTAINER_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
SRC_CBZ = CONTAINER_DIR / "test_cbz.cbz"
INNER_NAME = "inner.cbz"
OUTER_NAME = "outer.zip"
OUTER_TAR_NAME = "outer.tar"
ARGS = (PROGRAM_NAME, "-rvvtx", "ZIP,CBZ,TAR")


class TestNestedArchives:
    """Nested archives must unpack, optimize, and repack."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_cbz_nested_in_zip(self) -> None:
        """A CBZ inside a ZIP is optimized in place."""
        outer_path = TMP_ROOT / OUTER_NAME
        with ZipFile(outer_path, "w", compression=ZIP_STORED) as zf:
            zf.write(SRC_CBZ, INNER_NAME)
        orig_outer_size = outer_path.stat().st_size

        cli.main((*ARGS, str(TMP_ROOT)))

        assert outer_path.stat().st_size < orig_outer_size
        with ZipFile(outer_path, "r") as zf:
            assert zf.namelist() == [INNER_NAME]
            inner_bytes = zf.read(INNER_NAME)
        assert len(inner_bytes) < SRC_CBZ.stat().st_size
        # The optimized inner member must still be a readable zip.
        with ZipFile(BytesIO(inner_bytes), "r") as inner_zf:
            assert inner_zf.testzip() is None
            assert inner_zf.namelist()

    def test_cbz_nested_in_tar(self) -> None:
        """A CBZ inside an uncompressed tar is optimized in place."""
        outer_path = TMP_ROOT / OUTER_TAR_NAME
        with TarFile(outer_path, "w") as tf:
            tf.add(SRC_CBZ, INNER_NAME)
        orig_outer_size = outer_path.stat().st_size

        cli.main((*ARGS, str(TMP_ROOT)))

        assert outer_path.stat().st_size < orig_outer_size
        with TarFile(outer_path, "r") as tf:
            names = tf.getnames()
            assert INNER_NAME in names
            member = tf.extractfile(INNER_NAME)
            assert member is not None
            inner_bytes = member.read()
        assert len(inner_bytes) < SRC_CBZ.stat().st_size
        with ZipFile(BytesIO(inner_bytes), "r") as inner_zf:
            assert inner_zf.testzip() is None
            assert inner_zf.namelist()
