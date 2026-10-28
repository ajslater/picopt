"""Test MPO detection, optimization and conversion."""

import struct
import zipfile
from functools import cache
from io import BytesIO
from pathlib import Path

import mozjpeg_lossless_optimization
import pytest
from mozjpeg_lossless_optimization import COPY_MARKERS
from PIL import Image

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.config import PicoptConfig
from picopt.log.summary import Stats
from picopt.pillow import mpf
from picopt.plugins.mpo import MPO_FILE_FORMAT, JpegFromMpo, Mpo
from picopt.walk.walk import Walk
from tests import IMAGES_DIR, assert_size_close
from tests.doctor_util import find_row, isolate_config, run_doctor
from tests.mpo_util import (
    CAMERA_MPO,
    CONTAINER_XMP,
    build_mpo,
    make_mpo,
    xmp_segment_count,
)

__all__ = ()

# Expected camera fixture sizes. Size alone can't tell a correct result from
# a malformed one, so every test also checks the structure.
_CAMERA_OPTIMIZED_SIZE = 6571356
_CAMERA_CONVERTED_SIZE = 5963387
_CAMERA_EXTRACTED_SIZE = 6450055
_WARNING = "its format is MPO, not JPEG"


@cache
def _camera() -> bytes:
    return CAMERA_MPO.read_bytes()


@cache
def _phone() -> bytes:
    return make_mpo()


def _old_picopt_output(data: bytes) -> bytes:
    """Return what picopt 6.10 wrote for -c JPEG: the primary and a stale index."""
    return mozjpeg_lossless_optimization.optimize(data, copy=COPY_MARKERS.ALL)


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str) -> Stats:
    isolate_config(monkeypatch, tmp_path)
    arguments = cli.get_arguments((PROGRAM_NAME, "-q", *args))
    return Walk(PicoptConfig().get_config(arguments)).walk()


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / "images" / name
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(data)
    return path


def _frames(data: bytes) -> list[bytes]:
    """Decode every image in the file."""
    with Image.open(BytesIO(data)) as image:
        frames = []
        for number in range(getattr(image, "n_frames", 1)):
            image.seek(number)
            frames.append(image.tobytes())
    return frames


def _info(data: bytes) -> tuple[str | None, dict]:
    with Image.open(BytesIO(data)) as image:
        return image.format, dict(image.info)


def _split(data: bytes) -> tuple[bytes, ...]:
    index = mpf.parse(data)
    assert index is not None
    return mpf.split(data, index)


class TestNotEnabled:
    """Without -x MPO, an MPO is skipped, with a warning when named as a JPEG."""

    def test_jpeg_suffix_warns(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        paths = [
            _write(tmp_path, name, _phone())
            for name in ("IMG_0001.jpeg", "IMG_0002.JPG")
        ]
        stats = _run(monkeypatch, tmp_path, "-r", str(paths[0].parent))
        assert all(path.read_bytes() == _phone() for path in paths)
        assert stats.skipped == len(paths)
        assert not stats.errors
        assert {path for path, _ in stats.warnings} == set(paths)
        for _, message in stats.warnings:
            assert _WARNING in message
            assert "-x MPO to optimize it, or -x MPO -c JPEG" in message

    def test_mpo_suffix_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "stereo.mpo", _phone())
        stats = _run(monkeypatch, tmp_path, str(path))
        assert stats.skipped == 1
        assert not stats.warnings

    def test_enabled_but_unavailable_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The startup banner and the doctor already explain this one."""
        path = _write(tmp_path, "IMG.jpeg", _phone())
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", "-D", "mozjpeg", str(path))
        assert stats.skipped == 1
        assert not stats.warnings
        assert path.read_bytes() == _phone()

    def test_plain_jpeg_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """MPO keeps .jpg names without claiming them, so -f MPO skips JPEGs quietly."""
        jpeg_bytes = (IMAGES_DIR / "test_jpg.jpg").read_bytes()
        names = ("plain.jpg", "plain.jpeg", "converted.mpo")
        paths = [_write(tmp_path, name, jpeg_bytes) for name in names]
        stats = _run(monkeypatch, tmp_path, "-f", "MPO", "-r", str(paths[0].parent))
        assert stats.skipped == len(names)
        assert not stats.warnings

    def test_archive_member(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        path = tmp_path / "images" / "book.cbz"
        path.parent.mkdir()
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("IMG.jpeg", _phone())

        stats = _run(monkeypatch, tmp_path, "-x", "CBZ", str(path))
        [(warning_path, message)] = stats.warnings
        assert warning_path is None
        assert message.startswith(f"{path}:IMG.jpeg: ")
        assert _WARNING in message

        stats = _run(monkeypatch, tmp_path, "-x", "CBZ,MPO", str(path))
        assert not stats.warnings
        assert not stats.errors
        with zipfile.ZipFile(path) as archive:
            member = archive.read("IMG.jpeg")
        assert len(member) < len(_phone())
        assert _frames(member) == _frames(_phone())


class TestOptimize:
    """-x MPO optimizes every image and keeps the file an MPO."""

    @pytest.mark.parametrize("source", [_camera, _phone], ids=["camera", "phone"])
    def test_keeps_every_image(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source
    ) -> None:
        original = source()
        path = _write(tmp_path, "IMG_0001.jpeg", original)
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        assert not stats.errors
        optimized = path.read_bytes()
        assert len(optimized) < len(original)
        assert _info(optimized)[0] == "MPO"
        assert len(_split(optimized)) == len(_split(original))
        assert _frames(optimized) == _frames(original)

        stats = _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        assert not stats.errors
        assert path.read_bytes() == optimized

    def test_camera_size(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _write(tmp_path, "IMG.jpeg", _camera())
        _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        assert_size_close(path.stat().st_size, _CAMERA_OPTIMIZED_SIZE)

    def test_strip_metadata_keeps_structure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """-M would strip the index and the gain map's own XMP, so it's ignored."""
        kept = _write(tmp_path, "kept.jpeg", _phone())
        stripped = _write(tmp_path, "stripped.jpeg", _phone())
        _run(monkeypatch, tmp_path, "-x", "MPO", str(kept))
        _run(monkeypatch, tmp_path, "-x", "MPO", "-M", str(stripped))
        assert stripped.read_bytes() == kept.read_bytes() != _phone()

    def test_gcontainer_keeps_appended_images(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        original = make_mpo(xmp=CONTAINER_XMP)
        path = _write(tmp_path, "IMG.jpg", original)
        _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        primary, gain_map = _split(path.read_bytes())
        original_primary, original_gain_map = _split(original)
        assert gain_map == original_gain_map
        assert len(primary) < len(original_primary)

    def test_undecodable_image_is_kept(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An image mozjpeg can't read is copied, and the rest optimized."""
        primary = _split(_phone())[0]
        # Segments through SOS and an EOI, but no frame header to decode.
        undecodable = b"\xff\xd8\xff\xda\x00\x02" + b"\x00" * 64 + b"\xff\xd9"
        original = build_mpo([mpf.strip(primary), undecodable])
        path = _write(tmp_path, "IMG.jpeg", original)
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        assert not stats.errors
        optimized_primary, kept = _split(path.read_bytes())
        assert kept == undecodable
        assert len(optimized_primary) < len(_split(original)[0])

    def test_stale_primary_size_is_an_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        Software that doesn't know MPF grew a segment ahead of the index.

        The primary's declared size is now short. Cutting it there would lose
        the bottom of the photo in either mode, so the file is left alone.
        """
        phone = _phone()
        comment = b"\xff\xfe" + struct.pack(">H", 2 + 40) + b"x" * 40
        edited = phone[:2] + comment + phone[2:]
        path = _write(tmp_path, "IMG.jpeg", edited)
        for args in (("-x", "MPO"), ("-x", "MPO", "-c", "JPEG")):
            stats = _run(monkeypatch, tmp_path, *args, str(path))
            [(_, message)] = stats.errors
            assert "isn't where the MP Index says" in message
            assert path.read_bytes() == edited

    def test_malformed_is_an_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        broken = _old_picopt_output(_phone())
        path = _write(tmp_path, "IMG.jpeg", broken)
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", str(path))
        [(_, message)] = stats.errors
        assert "malformed MPO" in message
        assert path.read_bytes() == broken


class TestConvert:
    """-x MPO -c JPEG keeps only the primary image, as a plain JPEG."""

    def test_primary_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "IMG_0001.jpeg", _phone())
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", str(path))
        assert not stats.errors
        converted = path.read_bytes()
        image_format, info = _info(converted)
        assert image_format == "JPEG"
        assert mpf.parse(converted) is None
        assert xmp_segment_count(converted) == 1
        assert info.get("exif")
        assert info.get("icc_profile")
        assert _frames(converted) == _frames(_phone())[:1]

        stats = _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", str(path))
        assert not stats.errors
        assert path.read_bytes() == converted

    def test_strip_metadata(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "IMG.jpeg", _phone())
        _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", "-M", str(path))
        image_format, info = _info(path.read_bytes())
        assert image_format == "JPEG"
        assert not {"exif", "xmp", "icc_profile"} & set(info)

    def test_mpo_suffix_keeps_name(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Renaming to .jpg would overwrite the JPEG stereo cameras save beside it."""
        path = _write(tmp_path, "DSCF0001.MPO", _phone())
        beside = _write(tmp_path, "DSCF0001.JPG", b"the camera's own JPEG")
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", str(path))
        assert not stats.errors
        assert _info(path.read_bytes())[0] == "JPEG"
        assert beside.read_bytes() == b"the camera's own JPEG"

    def test_camera_size(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _write(tmp_path, "IMG.jpeg", _camera())
        _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", str(path))
        converted = path.read_bytes()
        assert mpf.parse(converted) is None
        assert_size_close(len(converted), _CAMERA_CONVERTED_SIZE)

    def test_without_mozjpeg(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "IMG.jpeg", _camera())
        args = ("-x", "MPO", "-c", "JPEG", "-D", "mozjpeg", str(path))
        stats = _run(monkeypatch, tmp_path, *args)
        assert not stats.errors
        extracted = path.read_bytes()
        assert _info(extracted)[0] == "JPEG"
        assert mpf.parse(extracted) is None
        assert xmp_segment_count(extracted) == 1
        assert_size_close(len(extracted), _CAMERA_EXTRACTED_SIZE)

    def test_repairs_old_picopt_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        broken = _old_picopt_output(_phone())
        assert _info(broken)[0] == "MPO"
        path = _write(tmp_path, "IMG.jpeg", broken)
        stats = _run(monkeypatch, tmp_path, "-x", "MPO", "-c", "JPEG", str(path))
        assert not stats.errors
        repaired = path.read_bytes()
        assert _info(repaired)[0] == "JPEG"
        assert _frames(repaired) == _frames(_phone())[:1]


class TestRouting:
    def test_routes(self) -> None:
        assert registry.routes_by_format()[MPO_FILE_FORMAT] == (Mpo, (JpegFromMpo,))

    @pytest.mark.parametrize(
        ("convert_to", "expected"),
        [(frozenset(), Mpo), (frozenset({"JPEG"}), JpegFromMpo)],
    )
    def test_pick(self, convert_to: frozenset[str], expected: type) -> None:
        native, convert_chain = registry.routes_by_format()[MPO_FILE_FORMAT]
        picked = registry.pick_route_handler(
            MPO_FILE_FORMAT,
            native,
            convert_chain,
            convert=True,
            repack=False,
            convert_to=convert_to,
            handler_stages=dict.fromkeys((Mpo, JpegFromMpo), ()),
        )
        assert picked is expected

    def test_off_by_default(self) -> None:
        assert "MPO" in registry.all_format_strs()
        assert "MPO" not in cli._default_format_strs()

    @pytest.mark.parametrize(
        ("args", "row"),
        [
            (("-x", "MPO"), "ok MPO Mpo: mozjpeg"),
            (
                ("-x", "MPO", "-c", "JPEG", "-D", "mozjpeg"),
                "ok MPO to JPEG with JpegFromMpo: mpo_extract (mozjpeg missing, optional)",
            ),
        ],
    )
    def test_doctor(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        args: tuple[str, ...],
        row: str,
    ) -> None:
        isolate_config(monkeypatch, tmp_path)
        _, out = run_doctor(capsys, *args)
        assert find_row(out, "ok", "MPO") == row
