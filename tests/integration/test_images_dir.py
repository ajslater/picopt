"""Test comic format."""
import platform
import shutil

from picopt import PROGRAM_NAME, cli
from tests import IMAGES_DIR, get_test_dir


__all__ = ()
TMP_ROOT = get_test_dir()
FNS = {
    "07themecamplist.pdf": (93676, 93676, ("pdf", 93676), ("pdf", 93676)),
    "test_animated_gif.gif": (16383, 16358, ("gif", 16358), ("webp", 11846)),
    "test_animated_png.png": (63435, 63435, ("png", 63435), ("webp", 54324)),
    "test_animated_webp.webp": (13610, 11854, ("webp", 11854), ("webp", 11854)),
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
        8914,
        8914,
        ("webp", 8914),
        ("webp", 8914),
    ),
    "mri.tif": (230578, 230578, ("tif", 230578), ("webp", 128416)),
}
if platform.system() == "Darwin":
    FNS.update(
        {
            "test_bmp.bmp": (141430, 141430, ("png", 67215), ("webp", 47524)),
            "test_gif.gif": (138952, 138944, ("png", 112467), ("webp", 26504)),
            "test_jpg.jpg": (97373, 87913, ("jpg", 87913), ("jpg", 87913)),
            "test_png_16rgba.png": (3435, 2870, ("png", 2870), ("webp", 1142)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12808)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197726),
            ),
            "test_webp_lossy.webp": (2764, 1714, ("webp", 1714), ("webp", 1714)),
            "test_webp_lossy_pre-optimized.webp": (
                1508,
                1508,
                ("webp", 1508),
                ("webp", 1508),
            ),
            "eight.tif": (59640, 59640, ("png", 30564), ("webp", 24974)),
        }
    )
else:
    FNS.update(
        {
            "test_bmp.bmp": (141430, 141430, ("png", 67215), ("webp", 47524)),
            "test_gif.gif": (138952, 138944, ("png", 112467), ("webp", 26504)),
            "test_jpg.jpg": (97373, 87922, ("jpg", 87922), ("jpg", 87922)),
            "test_png_16rgba.png": (3435, 2870, ("png", 2870), ("webp", 1142)),
            "test_pnm.pnm": (27661, 27661, ("png", 15510), ("webp", 12808)),
            "test_pre-optimized_png.png": (
                256572,
                256572,
                ("png", 256572),
                ("webp", 197680),
            ),
            "test_webp_lossy.webp": (2764, 1760, ("webp", 1760), ("webp", 1760)),
            "test_webp_lossy_pre-optimized.webp": (  # XXX SHOULD NOT CONVERT MORE?
                1508,
                1506,
                ("webp", 1506),
                ("webp", 1506),
            ),
            "eight.tif": (59640, 59640, ("png", 30564), ("webp", 24982)),
        }
    )


class TestImagesDir:
    def setup_method(self) -> None:
        self.teardown_method()
        shutil.copytree(IMAGES_DIR, TMP_ROOT)
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[0]

    def teardown_method(self) -> None:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def test_no_convert(self) -> None:
        args = (PROGRAM_NAME, "-rvv", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = TMP_ROOT / name
            assert path.stat().st_size == sizes[1]

    def test_convert_to_png(self) -> None:
        args = (PROGRAM_NAME, "-rvvx", "TIFF", "-c", "PNG", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[2][0])
            assert path.stat().st_size == sizes[2][1]

    def test_convert_to_webp(self) -> None:
        args = (PROGRAM_NAME, "-rvvx", "TIFF", "-c", "WEBP", str(TMP_ROOT))
        res = cli.main(args)
        assert res
        for name, sizes in FNS.items():
            path = (TMP_ROOT / name).with_suffix("." + sizes[3][0])
            assert path.stat().st_size == sizes[3][1]
