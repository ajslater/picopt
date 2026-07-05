#!/usr/bin/env python3
"""
Benchmark picopt wall-clock time and peak RSS over synthetic corpora.

Builds corpora from the test fixtures (an archive-heavy one and an
image-heavy one), runs picopt as a subprocess, and reports wall time and
the peak resident set size of the whole process tree.

Usage:
    uv run python bin/benchmark.py [--archives N] [--images N] [--keep]
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tempfile import mkdtemp

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = REPO_ROOT / "tests" / "test_files"
CONTAINER_SRCS = ("test_cbz.cbz",)
IMAGE_SRCS = (
    "test_png.png",
    "test_jpg.jpg",
    "test_gif.gif",
    "test_webp_lossless.webp",
    "test_animated_gif.gif",
)
# /usr/bin/time peak-RSS line: bytes on darwin (-l), kilobytes on linux (-v).
_IS_DARWIN = sys.platform == "darwin"
_TIME_ARGS = ("/usr/bin/time", "-l" if _IS_DARWIN else "-v")
_RSS_RE = re.compile(
    r"^\s*(\d+)\s+maximum resident set size"
    if _IS_DARWIN
    else r"Maximum resident set size[^:]*:\s*(\d+)",
    re.MULTILINE,
)
_RSS_DIVISOR = 1024 * 1024 if _IS_DARWIN else 1024


def _build_corpus(root: Path, n_archives: int, n_images: int) -> None:
    archive_dir = root / "archives"
    archive_dir.mkdir(parents=True)
    for i in range(n_archives):
        src = FIXTURES / "containers" / CONTAINER_SRCS[i % len(CONTAINER_SRCS)]
        shutil.copy(src, archive_dir / f"comic_{i:04d}.cbz")
    image_dir = root / "images"
    image_dir.mkdir(parents=True)
    for i in range(n_images):
        src = FIXTURES / "images" / IMAGE_SRCS[i % len(IMAGE_SRCS)]
        shutil.copy(src, image_dir / f"img_{i:04d}{src.suffix}")


def _run(args: tuple[str, ...], target: Path) -> tuple[float, int, int]:
    """Run picopt over target; return (seconds, peak_rss_mib, returncode)."""
    start = time.perf_counter()
    proc = subprocess.run(  # noqa: S603
        (
            *_TIME_ARGS,
            sys.executable,
            "-c",
            "from picopt.cli import main; main()",
            *args,
            str(target),
        ),
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    elapsed = time.perf_counter() - start
    stderr = proc.stderr.decode(errors="replace")
    match = _RSS_RE.search(stderr)
    peak_mib = int(match.group(1)) // _RSS_DIVISOR if match else -1
    if proc.returncode:
        print(proc.stdout.decode(errors="replace")[-2000:])
        print(stderr[-2000:])
    return elapsed, peak_mib, proc.returncode


def main() -> None:
    """Build corpora and run the benchmark scenarios."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=int, default=100)
    parser.add_argument("--images", type=int, default=300)
    parser.add_argument(
        "--keep", action="store_true", help="Keep the corpus dir afterwards"
    )
    opts = parser.parse_args()

    root = Path(mkdtemp(prefix="picopt-bench-"))
    _build_corpus(root, opts.archives, opts.images)
    print(f"corpus: {root} ({opts.archives} archives, {opts.images} images)")

    scenarios = (
        ("archives cold", ("-rx", "CBZ,PNG,JPEG,GIF,WEBP"), root / "archives"),
        ("images cold", ("-rx", "PNG,JPEG,GIF,WEBP"), root / "images"),
        ("images quiet", ("-q", "-rx", "PNG,JPEG,GIF,WEBP"), root / "images"),
    )
    try:
        print(f"{'scenario':<16} {'seconds':>8} {'peak MiB':>9} {'rc':>3}")
        for name, args, target in scenarios:
            elapsed, peak, rc = _run(args, target)
            print(f"{name:<16} {elapsed:>8.2f} {peak:>9} {rc:>3}")
    finally:
        if opts.keep:
            print(f"kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
