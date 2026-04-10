"""
Tests for the PDF plugin.

Mirrors :mod:`tests.test_containers`: parametrized over fixture filename,
with a setup fixture that copies the source PDF into a per-module tmp
dir before each run. Adds a lossless-render check on top: every fixture
that picopt actually rewrites is rasterized at 150 DPI through pdftoppm
and the pixels are SHA256-compared against the original. Any non-zero
diff is a bug per the handoff doc's bit-identical requirement.

Fixture inventory
-----------------

Synthesizable from pikepdf alone (built into ``tests/test_files/pdf/``
on first test run by :mod:`tests._build_pdf_fixtures`):

    photo_jpeg.pdf      DCT image, expected to shrink ~30%
    smask.pdf           DCT image with Flate-encoded alpha SMask, shrinks
    text_bloated.pdf    Uncompressed text streams, shrinks ~88% (qpdf only)
    text_optimized.pdf  Already qpdf-max, expected unchanged
    signed.pdf          AcroForm SigFlags=3, expected refused
    encrypted.pdf       Password-protected, expected refused
    multi_filter.pdf    [/ASCII85Decode /DCTDecode] image, plugin skips it
    bilevel_ccitt.pdf   CCITTFaxDecode bilevel image, plugin skips image
    inline_images.pdf   Inline image inside content stream, plugin doesn't
                        see it (content stream survives intact)
    latex.pdf           See test_latex_pdf_renders_losslessly below
    jbig2.pdf           See test_jbig2_pdf_unchanged below
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from types import MappingProxyType

import pikepdf
import pytest

from picopt import PROGRAM_NAME, cli
from tests import assert_size_close, get_test_dir
from tests.base import BaseTest

__all__ = ()

PDF_FIXTURE_DIR = Path(__file__).parent / "test_files" / "pdf"

# ---------------------------------------------------------------------------
# Fixture inventory and expected outcomes
# ---------------------------------------------------------------------------


class Outcome:
    """What we expect picopt -x PDF to do to a given fixture."""

    SHRINKS = "shrinks"
    """Output strictly smaller than input. Used for fixtures that exercise
    a specific savings path (mozjpeg, structural Flate, or both)."""

    UNCHANGED = "unchanged"
    """Picopt rewrote the file, found the result was not smaller, and
    kept the original byte-for-byte. Used for already-optimized fixtures
    and for ones where the only image is in a format the plugin
    deliberately skips."""

    REFUSED = "refused"
    """Picopt errored out without modifying the file. Used for signed and
    encrypted PDFs."""


# Fixture filename -> (outcome, minimum savings %, lossless-render check,
#                      source size in bytes)
#
# minimum_savings is only consulted for SHRINKS rows. It's a soft floor
# that protects against silent regressions in mozjpeg/qpdf without
# pinning exact byte counts (which would break the moment Pillow ships
# a new JPEG encoder).
#
# render_check=True means rasterize both files at 150 DPI and require
# pixel-identical output. Only meaningful for SHRINKS rows (UNCHANGED
# rows are byte-identical so rendering is tautological, REFUSED rows
# weren't modified at all).
#
# source_size is checked through assert_size_close at copy time so we
# notice if a fixture gets corrupted or accidentally rebuilt with very
# different parameters, while still tolerating the small drift pikepdf
# introduces between versions.
FIXTURES: MappingProxyType[str, tuple[str, int, bool, int]] = MappingProxyType(
    {
        "photo_jpeg.pdf": (Outcome.SHRINKS, 20, True, 30543),
        "smask.pdf": (Outcome.SHRINKS, 15, True, 9803),
        "text_bloated.pdf": (Outcome.SHRINKS, 50, True, 32086),
        "text_optimized.pdf": (Outcome.UNCHANGED, 0, False, 2117),
        "multi_filter.pdf": (Outcome.UNCHANGED, 0, False, 11255),
        "bilevel_ccitt.pdf": (Outcome.UNCHANGED, 0, False, 3397),
        "inline_images.pdf": (Outcome.UNCHANGED, 0, False, 623),
        "signed.pdf": (Outcome.REFUSED, 0, False, 577),
        "encrypted.pdf": (Outcome.REFUSED, 0, False, 921),
    }
)

# Source sizes for the fixtures that don't fit the
# parametrized FIXTURES schema. Same tolerance semantics as above.
HUNTED_SOURCE_SIZES: MappingProxyType[str, int] = MappingProxyType(
    {
        "latex.pdf": 288814,
        "jbig2.pdf": 1624,
    }
)

TMP_ROOT = get_test_dir()
ARGS = (PROGRAM_NAME, "-vvx", "PDF")
HAS_PDFTOPPM = shutil.which("pdftoppm") is not None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_picopt(path: Path) -> None:
    """Invoke picopt -x PDF on a single file."""
    args = (*ARGS, str(path))
    cli.main(args)


def _rasterize_hash(pdf_path: Path, tmp_dir: Path) -> str:
    """
    Render every page at 150 DPI grayscale and SHA256 the bytes.

    Uses pdftoppm because it's the deterministic poppler renderer the
    handoff doc recommends. Hashing the raw .pgm output (header +
    pixels) catches any pixel-level rendering difference between input
    and output. Caller is responsible for skipping if pdftoppm is
    missing.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    prefix = tmp_dir / "page"
    subprocess.run(  # noqa: S603
        ("pdftoppm", "-r", "150", "-gray", str(pdf_path), str(prefix)),  # noqa: S607
        check=True,
        capture_output=True,
    )
    h = hashlib.sha256()
    for page in sorted(tmp_dir.glob("page-*.pgm")):
        h.update(page.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Synthesizable fixtures: full pipeline test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", FIXTURES)
class TestPdfFixtures(BaseTest):
    """Run picopt -x PDF against every synthesized fixture."""

    TMP_ROOT: Path = TMP_ROOT
    SOURCE_DIR: Path = PDF_FIXTURE_DIR
    # BaseTest's setup fixture asserts source size against FNS[fn][0]
    # using strict equality, which is too tight for pikepdf-generated
    # fixtures (output drifts across versions). Override to keep an
    # equivalent sanity check via assert_size_close instead, which
    # tolerates that drift while still catching gross fixture corruption.
    FNS: MappingProxyType[str, tuple] = MappingProxyType({})

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, fn: str):
        """Override BaseTest's setup to use a tolerant source-size check."""
        self.teardown_method()
        self.TMP_ROOT.mkdir(parents=True)
        src = self.SOURCE_DIR / fn
        dest = self.TMP_ROOT / fn
        shutil.copy(src, dest)
        assert_size_close(dest.stat().st_size, FIXTURES[fn][3])
        yield
        self.teardown_method()

    def test_picopt_pdf_outcome(self, fn: str) -> None:
        """Picopt produces the expected file-size outcome for each fixture."""
        path = TMP_ROOT / fn
        source = PDF_FIXTURE_DIR / fn
        before = source.stat().st_size
        outcome, min_savings, _, _ = FIXTURES[fn]

        _run_picopt(path)

        after = path.stat().st_size

        if outcome == Outcome.SHRINKS:
            assert after < before, f"{fn}: expected shrink, got {before} -> {after}"
            saved_pct = (before - after) * 100 / before
            assert saved_pct >= min_savings, (
                f"{fn}: expected ≥{min_savings}% saved, got {saved_pct:.1f}%"
            )
        elif outcome == Outcome.UNCHANGED:
            assert after == before, (
                f"{fn}: expected byte-identical, got {before} -> {after}"
            )
        elif outcome == Outcome.REFUSED:
            assert after == before, (
                f"{fn}: refused fixture must be unchanged on disk, "
                f"got {before} -> {after}"
            )
            # Original file content must survive verbatim (not just same
            # length): the refused-PDF guarantee is "we did not touch it".
            assert path.read_bytes() == source.read_bytes(), (
                f"{fn}: refused fixture bytes differ from source"
            )

    def test_picopt_pdf_still_parses(self, fn: str) -> None:
        """Whatever picopt produced (or left behind) must still be a valid PDF."""
        path = TMP_ROOT / fn
        _run_picopt(path)

        # Encrypted is the special case: it must still parse, but only
        # with the password used during fixture construction.
        if fn == "encrypted.pdf":
            with pikepdf.open(path, password="user") as pdf:  # noqa: S106
                assert len(pdf.pages) >= 1
        else:
            with pikepdf.open(path) as pdf:
                assert len(pdf.pages) >= 1

    @pytest.mark.skipif(
        not HAS_PDFTOPPM,
        reason="pdftoppm (poppler-utils) not installed",
    )
    def test_picopt_pdf_lossless_render(self, fn: str, tmp_path: Path) -> None:
        """For SHRINKS fixtures, rendered pixels must match the original at 150 DPI."""
        outcome, _, render_check, _ = FIXTURES[fn]
        if not render_check:
            pytest.skip(f"{fn}: render check not applicable for {outcome}")

        path = TMP_ROOT / fn
        source = PDF_FIXTURE_DIR / fn

        original_hash = _rasterize_hash(source, tmp_path / "orig")

        _run_picopt(path)

        optimized_hash = _rasterize_hash(path, tmp_path / "opt")

        assert original_hash == optimized_hash, (
            f"{fn}: rendered output differs after optimization "
            f"(orig={original_hash[:12]} opt={optimized_hash[:12]})"
        )


# ---------------------------------------------------------------------------
# Embedded JPEG round-trip: per-image pixel hash check
# ---------------------------------------------------------------------------


class TestPdfEmbeddedJpegLossless:
    """
    Check that mozjpeg's lossless guarantee survives the PDF round-trip.

    Decode the embedded JPEGs out of both the source and
    the optimized output, hash the decoded pixels, require equality.

    This is a finer-grained complement to the pdftoppm render check —
    pdftoppm catches *any* rendering diff including font/content stream
    issues; this catches *only* image diffs but does so without needing
    a renderer at all, so it runs even on machines without poppler.
    """

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def teardown_method(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    @staticmethod
    def _image_pixel_hashes(pdf_path: Path) -> list[str]:
        hashes = []
        with pikepdf.open(pdf_path) as pdf:
            for obj in pdf.objects:
                if not isinstance(obj, pikepdf.Stream):
                    continue
                if obj.get(pikepdf.Name.Subtype) != pikepdf.Name.Image:
                    continue
                pim = pikepdf.PdfImage(obj)
                pil = pim.as_pil_image()
                hashes.append(hashlib.sha256(pil.tobytes()).hexdigest())
        return hashes

    @pytest.mark.parametrize("fn", ["photo_jpeg.pdf", "smask.pdf"])
    def test_embedded_jpeg_pixels_unchanged(self, fn: str) -> None:
        source = PDF_FIXTURE_DIR / fn
        path = TMP_ROOT / fn
        shutil.copy(source, path)
        assert_size_close(path.stat().st_size, FIXTURES[fn][3])

        orig_hashes = self._image_pixel_hashes(source)
        assert orig_hashes, f"{fn}: no images found in source"

        _run_picopt(path)

        opt_hashes = self._image_pixel_hashes(path)
        assert opt_hashes == orig_hashes, (
            f"{fn}: decoded image pixels changed after optimization"
        )


def _maybe_skip_missing(name: str) -> Path:
    path = PDF_FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not present in {PDF_FIXTURE_DIR}")
    return path


class TestPdfHuntedFixtures:
    """New Tests."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def teardown_method(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_latex_pdf_renders_losslessly(self, tmp_path: Path) -> None:
        """latex.pdf — a real LaTeX-produced PDF."""
        path_src = PDF_FIXTURE_DIR / "latex.pdf"
        if not HAS_PDFTOPPM:
            pytest.skip("pdftoppm not installed")
        path = TMP_ROOT / "latex.pdf"
        shutil.copy(path_src, path)
        assert_size_close(path.stat().st_size, HUNTED_SOURCE_SIZES["latex.pdf"])

        original_hash = _rasterize_hash(path_src, tmp_path / "orig")
        _run_picopt(path)
        optimized_hash = _rasterize_hash(path, tmp_path / "opt")

        assert original_hash == optimized_hash, (
            "latex.pdf: rendered output differs after optimization"
        )

    def test_jbig2_pdf_unchanged(self) -> None:
        """jbig2.pdf — a PDF with at least one JBIG2-encoded bilevel image."""
        path_src = _maybe_skip_missing("jbig2.pdf")
        path = TMP_ROOT / "jbig2.pdf"
        shutil.copy(path_src, path)
        assert_size_close(path.stat().st_size, HUNTED_SOURCE_SIZES["jbig2.pdf"])
        before = path.stat().st_size

        _run_picopt(path)

        after = path.stat().st_size
        assert after <= before, (
            f"jbig2.pdf grew during optimization ({before} -> {after})"
        )
        with pikepdf.open(path) as pdf:
            assert len(pdf.pages) >= 1
            jbig2_count = 0
            for obj in pdf.objects:
                if not isinstance(obj, pikepdf.Stream):
                    continue
                filt = obj.get(pikepdf.Name.Filter)
                if filt == pikepdf.Name.JBIG2Decode:
                    jbig2_count += 1
                    # Must still decode.
                    pikepdf.PdfImage(obj).as_pil_image()
            assert jbig2_count >= 1, "jbig2.pdf has no JBIG2 streams — wrong fixture"
