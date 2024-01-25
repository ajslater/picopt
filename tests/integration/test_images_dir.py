"""Test comic format."""
import platform
import shutil

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir

__all__ = ()
TMP_ROOT = get_test_dir()
FNS = {
    "07themecamplist.pdf": (93676, 93676, ("pdf", 93676), ("pdf", 93676)),
    "test_animated_gif.gif": (16383, 16358, ("gif", 16358), ("webp", 11866)),
    "test_animated_png.png": (63435, 63435, ("png", 63435), ("webp", 43064)),
    "test_animated_webp.webp": (13610, 13610, ("webp", 13610), ("webp", 13610)),
    "test_png.png": (7967, 4379, ("png", 4379), ("webp", 3870)),
    "test_pre-optimized_jpg.jpg": (
        22664,
        22664,
        ("jpg", 22664),
        ("jpg", 22664),
    ),
    "test_txt.txt": (6, 6, ("txt", 6), ("txt", 6)),
    "test_webp_lossless.webp": (5334, 3870, ("webp", 3870), ("webp", 3870)),
    "test_webp_lossless_pre-optimized.webp": (
        4036,
        4036,
        ("webp", 4036),
        ("webp", 4036),
    ),
    "mri.tif": (230578, 230578, ("tif", 230578), ("webp", 83822)),
    "test_webp_lossy.webp": (2764, 2764, ("webp", 2764), ("webp", 2764)),
    "test_webp_lossy_pre-optimized.webp": (
        1508,
        1508,
        ("webp", 1508),
        ("webp", 1508),
    ),
}
if platform.system() == "Darwin":
    FNS.update(
        {
            "test_bmp.bmp": (141430, 141430, ("png", 67215), ("webp", 30814)),
            "test_gif.gif": (138952, 138944, ("png", 112467), ("webp", 107924)),
            "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
            "test_png_16rgba.png": (3435, 2870, ("png", 2870), ("webp", 728)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 6852)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 107984),
            ),
            "eight.tif": (59640, 59640, ("png", 30564), ("webp", 19436)),
        }
    )
else:
    FNS.update(
        {
            "test_bmp.bmp": (141430, 141430, ("png", 67215), ("webp", 30774)),
            "test_gif.gif": (138952, 138944, ("png", 112467), ("webp", 107952)),
            "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
            "test_png_16rgba.png": (3435, 2870, ("png", 2870), ("webp", 728)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 6852)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 108254),
            ),
            "eight.tif": (59640, 59640, ("png", 30564), ("webp", 19440)),
        }
    )


class TestImagesDir:
    """Test images dir."""

    def setup_method(self) -> None:
        """Set up method."""
        self.teardown_method()
        shutil.copytree(IMAGES_DIR, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        """Tear down method."""
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_no_convert(self) -> None:
        """Test no convert."""
        args = (PROGRAM_NAME, "-rvv", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[1]

    def test_convert_to_png(self) -> None:
        """Test convert to PNG."""
        args = (PROGRAM_NAME, "-rvvx", "TIFF", "-c", "PNG", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]

    def test_convert_to_webp(self) -> None:
        """Test convert to WEBP."""
        args = (PROGRAM_NAME, "-rvvx", "TIFF", "-c", "WEBP", str(TMP_ROOT))
        cli.main(args)
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[3][0])
            assert path.stat().st_size == sizes[3][1]
