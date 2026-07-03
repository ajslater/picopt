"""Test that svgo runs with a lossless, metadata-respecting configuration."""

import shutil
from collections.abc import Iterator

import pytest

from picopt import PROGRAM_NAME, cli
from tests import get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
SVG_FN = "boxed.svg"
# Enough repetitive filler that svgo produces a smaller file and picopt
# actually replaces it.
_SVG_RECT = (
    '  <rect x="{i}.0000" y="{i}.0000" width="10.0000" height="10.0000"'
    ' style="fill:#ff0000;stroke:none" />\n'
)
SVG_SOURCE = "".join(
    (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n',
        "  <title>Keep Me</title>\n",
        "  <desc>Important description</desc>\n",
        *(_SVG_RECT.format(i=i) for i in range(20)),
        "</svg>\n",
    )
)


class TestSvgLossless:
    """viewBox and metadata must survive optimization."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_viewbox_and_metadata_preserved(self) -> None:
        svg_path = TMP_ROOT / SVG_FN
        svg_path.write_text(SVG_SOURCE)
        orig_size = svg_path.stat().st_size

        cli.main((PROGRAM_NAME, "-rvx", "SVG", str(TMP_ROOT)))

        optimized = svg_path.read_text()
        assert svg_path.stat().st_size < orig_size
        assert "viewBox" in optimized
        assert "Keep Me" in optimized
        assert "Important description" in optimized

    def test_strip_metadata_still_keeps_viewbox(self) -> None:
        svg_path = TMP_ROOT / SVG_FN
        svg_path.write_text(SVG_SOURCE)

        cli.main((PROGRAM_NAME, "-rvMx", "SVG", str(TMP_ROOT)))

        optimized = svg_path.read_text()
        assert "viewBox" in optimized
        assert "Keep Me" not in optimized
