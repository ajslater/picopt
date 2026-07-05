"""Test container format conversion when no member produces work."""

import shutil
from collections.abc import Iterator
from tarfile import TarFile
from zipfile import ZipFile

import pytest

from picopt import PROGRAM_NAME, cli
from tests import get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
MEMBER_NAME = "readme.txt"
MEMBER_DATA = b"not an image\n"


class TestConvertContainerOnly:
    """--convert-to must repack even when every member is a noop."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_tar_with_only_noop_members_converts_to_zip(self) -> None:
        """A tar with no optimizable members still converts to zip."""
        member_path = TMP_ROOT / MEMBER_NAME
        member_path.write_bytes(MEMBER_DATA)
        tar_path = TMP_ROOT / "docs.tar"
        with TarFile(tar_path, "w") as tf:
            tf.add(member_path, MEMBER_NAME)
        member_path.unlink()

        cli.main((PROGRAM_NAME, "-rvx", "TAR,ZIP", "-c", "ZIP", str(TMP_ROOT)))

        zip_path = TMP_ROOT / "docs.zip"
        assert zip_path.exists()
        assert not tar_path.exists()
        with ZipFile(zip_path, "r") as zf:
            assert zf.read(MEMBER_NAME) == MEMBER_DATA
