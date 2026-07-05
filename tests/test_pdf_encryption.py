"""Test that repacking preserves PDF encryption for restricted files."""

import shutil
from collections.abc import Iterator
from io import BytesIO

import pikepdf
import pytest

from picopt import cli
from picopt.config import PicoptConfig
from picopt.path import PathInfo
from picopt.plugins.pdf import Pdf
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
SRC_PDF = IMAGES_DIR / "07themecamplist.pdf"
OWNER_PASSWORD = "owner-secret"  # noqa: S105


class TestPdfEncryptionPreserved:
    """Owner-password-restricted PDFs must not be silently decrypted."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_pack_into_keeps_owner_password_encryption(self) -> None:
        restricted_path = TMP_ROOT / "restricted.pdf"
        with pikepdf.open(SRC_PDF) as pdf:
            pdf.save(
                restricted_path,
                encryption=pikepdf.Encryption(owner=OWNER_PASSWORD, user=""),
            )
        # Opens without a password: only the owner permissions are locked.
        with pikepdf.open(restricted_path) as pdf:
            assert pdf.is_encrypted

        config = PicoptConfig().get_config(
            cli.get_arguments(("picopt", "-x", "PDF", str(TMP_ROOT)))
        )
        path_info = PathInfo(top_path=TMP_ROOT, path=restricted_path, convert=False)
        handler = Pdf(config, path_info, input_file_format=Pdf.OUTPUT_FILE_FORMAT)
        output_buffer = handler.pack_into()

        with pikepdf.open(BytesIO(output_buffer.getvalue())) as repacked:
            assert repacked.is_encrypted
