"""Test worker-side in-archive entry skipping and timestamp consumption."""

import pickle
import shutil
from collections.abc import Iterator
from zipfile import ZipFile, ZipInfo

import pytest
from treestamps.tree.config import TreestampsConfig

from picopt import PROGRAM_NAME, cli
from picopt.archive_stamps import ArchiveStamps
from picopt.config import PicoptConfig
from picopt.config.settings import PicoptSettings
from picopt.path import PathInfo
from picopt.plugins.zip import Cbz
from tests import IMAGES_DIR, get_test_dir

__all__ = ()

TMP_ROOT = get_test_dir()
PNG_BYTES = (IMAGES_DIR / "test_png.png").read_bytes()
STAMP = 1_900_000_000.0  # 2030 — after OLD_DATE, before NEW_DATE
OLD_DATE = (2020, 1, 1, 0, 0, 0)
NEW_DATE = (2035, 1, 1, 0, 0, 0)
CBZ_FN = "stamped.cbz"


def _make_config(*args: str) -> PicoptSettings:
    return PicoptConfig().get_config(
        cli.get_arguments(("picopt", "-rtvx", "CBZ,PNG", *args, str(TMP_ROOT)))
    )


def _make_cbz(members: dict[str, tuple], extra: dict[str, bytes] | None = None):
    zip_path = TMP_ROOT / CBZ_FN
    with ZipFile(zip_path, "w") as zf:
        for name, date_time in members.items():
            zf.writestr(ZipInfo(name, date_time=date_time), PNG_BYTES)
        for name, data in (extra or {}).items():
            zf.writestr(ZipInfo(name, date_time=OLD_DATE), data)
    return zip_path


def _make_handler(zip_path, config: PicoptSettings, stamps: ArchiveStamps | None):
    path_info = PathInfo(top_path=TMP_ROOT, path=zip_path, convert=False)
    handler = Cbz(
        config,
        path_info,
        input_file_format=Cbz.OUTPUT_FILE_FORMAT,
        timestamps=stamps,
        repack_handler_class=Cbz,
    )
    # walk() always executes in a worker; prove the machinery survives it.
    return pickle.loads(pickle.dumps(handler))  # noqa: S301


def _tree_config() -> TreestampsConfig:
    return TreestampsConfig(
        program_name=PROGRAM_NAME, path=TMP_ROOT, check_config=False
    )


def _walk_names(handler) -> tuple[set[str], set[str]]:
    yielded = {pi.name() for pi in handler.walk()}
    copied = {pi.name() for pi in handler.get_optimized_contents()}
    return yielded, copied


class TestInArchiveEntrySkip:
    """Members older than the archive's stamp skip optimization."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_old_entries_skip_and_new_entries_process(self) -> None:
        zip_path = _make_cbz({"old.png": OLD_DATE, "new.png": NEW_DATE})
        stamps = ArchiveStamps(_tree_config(), {str(zip_path): STAMP})
        handler = _make_handler(zip_path, _make_config(), stamps)
        yielded, copied = _walk_names(handler)
        assert yielded == {"new.png"}
        assert copied == {"old.png"}

    def test_ignore_entry_mtimes_flag_processes_everything(self) -> None:
        zip_path = _make_cbz({"old.png": OLD_DATE, "new.png": NEW_DATE})
        stamps = ArchiveStamps(_tree_config(), {str(zip_path): STAMP})
        handler = _make_handler(zip_path, _make_config("-E"), stamps)
        yielded, copied = _walk_names(handler)
        assert yielded == {"old.png", "new.png"}
        assert not copied

    def test_no_stamps_processes_everything(self) -> None:
        zip_path = _make_cbz({"old.png": OLD_DATE, "new.png": NEW_DATE})
        handler = _make_handler(zip_path, _make_config(), None)
        yielded, copied = _walk_names(handler)
        assert yielded == {"old.png", "new.png"}
        assert not copied


class TestInArchiveConsume:
    """.picopt_treestamps files inside archives are consumed and dropped."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_consumed_stamps_skip_members_and_drop_stamp_file(self) -> None:
        stamps = ArchiveStamps(_tree_config(), {})
        yaml_str = f"old.png: {STAMP}\n"
        zip_path = _make_cbz(
            {"old.png": OLD_DATE, "new.png": NEW_DATE},
            extra={stamps.filename: yaml_str.encode()},
        )
        handler = _make_handler(zip_path, _make_config(), stamps)
        yielded, copied = _walk_names(handler)
        assert yielded == {"new.png"}
        assert copied == {"old.png"}  # stamp member dropped, not copied
        assert handler.is_do_repack()

    def test_consumed_stamps_rejected_when_config_mismatch(self) -> None:
        tree_config = TreestampsConfig(
            program_name=PROGRAM_NAME,
            path=TMP_ROOT,
            check_config=True,
            program_config={"bigger": False},
            program_config_keys=("bigger",),
        )
        stamps = ArchiveStamps(tree_config, {})
        yaml_str = f"config:\n  bigger: true\nold.png: {STAMP}\n"
        zip_path = _make_cbz(
            {"old.png": OLD_DATE},
            extra={stamps.filename: yaml_str.encode()},
        )
        handler = _make_handler(zip_path, _make_config(), stamps)
        yielded, _ = _walk_names(handler)
        # The stamp does not match this run's config: old.png must process.
        assert yielded == {"old.png"}


class TestIncrementalArchiveRuns:
    """End to end: a member added with an old entry mtime is skipped."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self) -> Iterator[None]:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)
        yield
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_second_run_skips_old_dated_member(self) -> None:
        zip_path = _make_cbz({"first.png": (2025, 1, 1, 0, 0, 0)})
        cli.main((PROGRAM_NAME, "-rtvx", "CBZ,PNG", str(TMP_ROOT)))

        # Modify the archive: add an unoptimized member with an OLD entry
        # date. The archive's mtime is now newer than its stamp.
        with ZipFile(zip_path, "a") as zf:
            zf.writestr(ZipInfo("late.png", date_time=OLD_DATE), PNG_BYTES)

        cli.main((PROGRAM_NAME, "-rtvx", "CBZ,PNG", str(TMP_ROOT)))
        with ZipFile(zip_path, "r") as zf:
            # Entry mtime predates the stamp: member passed through as-is.
            assert zf.read("late.png") == PNG_BYTES

        cli.main((PROGRAM_NAME, "-rtvEx", "CBZ,PNG", str(TMP_ROOT)))
        with ZipFile(zip_path, "r") as zf:
            # -E ignores entry mtimes: the member finally gets optimized.
            assert len(zf.read("late.png")) < len(PNG_BYTES)
