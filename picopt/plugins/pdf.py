"""
PDF format plugin.

Owns: PDF.

Strategy
--------
Treat a PDF as a container of optimizable streams. The ContainerHandler base
gives us the standard walk → optimize-children-in-pool → repack lifecycle for
free; we just have to teach :class:`Pdf` how to enumerate the bits of a PDF
that picopt's existing handlers can shrink and how to put the file back
together afterwards.

Two sources of savings:

1. **Embedded JPEGs.** Every stream object whose ``/Subtype`` is ``/Image``
   and whose ``/Filter`` resolves to ``/DCTDecode`` is, byte-for-byte, a JPEG
   bitstream. We yield each one as a child :class:`PathInfo` carrying a
   synthetic ``.jpg`` archive entry name. picopt's existing detector then
   identifies the child as JPEG and dispatches it to the :class:`Jpeg`
   handler, which runs ``MozJpegTool`` (the same lossless mozjpeg pass used
   for standalone JPEGs). On repack we write any smaller result back into
   the original stream object, preserving its dictionary keys (``/ColorSpace``,
   ``/Width``, ``/Height``, ``/SMask``, etc) and ``/Length``.

   This is lossless in the strict sense the handoff document calls for: no
   DCT coefficients are touched, no fonts re-subset, no content streams
   semantically altered. ``-copy none`` (mozjpeg's default for our wrapper)
   strips JPEG APP markers, which is safe in PDF context because the PDF
   renderer reads colorspace/ICC from the ``/ColorSpace`` dict, not from
   the JPEG's APP segments.

2. **Structural recompression.** qpdf (via pikepdf) on save with
   ``recompress_flate=True`` and ``object_stream_mode=generate`` re-encodes
   every ``/FlateDecode`` stream at level 9 and bundles small dict objects
   into compressed object streams with a compressed xref. That handles
   content streams, font programs, XMP metadata, structure trees, and
   Flate-encoded images all at once.

Things deliberately not done
----------------------------
- **Zopfli post-pass.** The marginal 3-5% over qpdf level 9 is not worth
  pulling in a second slow dependency for an interactive tool. The handoff
  doc calls this skippable.
- **Inline images** (``BI ... ID ... EI``). Embedded directly in content
  streams, uncommon in modern PDFs, typically small.
- **Multi-filter arrays** like ``[/ASCII85Decode /DCTDecode]``. Vanishingly
  rare; we explicitly skip them rather than risk a corrupt rewrite.
- **JPEG 2000, JBIG2, CCITT Fax.** No lossless wins available.
- **Linearization.** Off by default; constrains object ordering and trades
  size for fast-web-view.

Refusals
--------
- Digitally signed PDFs (``/AcroForm /SigFlags`` bit 1) are refused: any
  byte change invalidates the signature. This is inherent, not a bug.
- Encrypted PDFs without a known password fail at open time and surface
  through the standard handler error path.
"""

from __future__ import annotations

from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zipfile import ZipInfo

from pikepdf.exceptions import PasswordError
from termcolor import cprint
from typing_extensions import override

from picopt.path import PathInfo
from picopt.plugins.base import (
    ContainerHandler,
    Detector,
    Handler,
    InternalTool,
    Plugin,
    Route,
    Tool,
)
from picopt.plugins.base.format import FileFormat

if TYPE_CHECKING:
    from collections.abc import Generator
    from io import BufferedReader

    from picopt.report import ReportStats

# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

_PDF_MAGIC: bytes = b"%PDF-"
# A leading-bytes scan window. Strict PDFs start at offset 0; some have a
# few junk bytes (BOM, mail headers) but the spec allows the marker within
# the first 1024 bytes.
_PDF_MAGIC_WINDOW: int = 1024


class PdfDetector(Detector):
    """Detect PDFs by magic bytes."""

    PRIORITY: int = 5

    @override
    @classmethod
    def identify(cls: type[PdfDetector], path_info: PathInfo) -> FileFormat | None:
        """Return Pdf.OUTPUT_FILE_FORMAT iff the file starts with %PDF-."""
        target = path_info.path_or_buffer()
        if isinstance(target, Path):
            try:
                with target.open("rb") as fp:
                    head = fp.read(_PDF_MAGIC_WINDOW)
            except OSError:
                return None
        else:
            target.seek(0)
            head = target.read(_PDF_MAGIC_WINDOW)
            target.seek(0)
        if _PDF_MAGIC in head:
            return Pdf.OUTPUT_FILE_FORMAT
        return None


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class PikepdfTool(InternalTool):
    """
    pikepdf (qpdf) PDF rewriter.

    Acts as the packing tool. The actual work — opening the PDF, swapping
    optimized stream bodies, and saving with maximum compression — lives on
    the :class:`Pdf` handler. This tool exists so the doctor command can
    probe pikepdf availability and so :class:`Pdf` participates in the
    standard PIPELINE plumbing.
    """

    name = "pikepdf"
    module_name = "pikepdf"

    @override
    def run_pack(self, handler: Handler) -> BytesIO:
        if not isinstance(handler, Pdf):
            msg = "PikepdfTool only packs Pdf handlers"
            raise TypeError(msg)
        return handler.pack_into()


_PIKEPDF_TOOL = PikepdfTool()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_dct_filter(filt: Any) -> bool:
    """
    Whether a stream's ``/Filter`` resolves to a single ``/DCTDecode``.

    Handles bare ``Name`` and length-1 ``Array`` cases. Multi-filter arrays
    (``[/ASCII85Decode /DCTDecode]`` and friends) are intentionally rejected:
    rewriting only the inner JPEG bitstream while leaving the outer wrapper
    in place is fragile and the case is vanishingly rare in modern PDFs.
    """
    if filt is None:
        return False
    # Lazy import: keep module import working when pikepdf is missing.
    import pikepdf

    if isinstance(filt, pikepdf.Name):
        return filt == pikepdf.Name.DCTDecode
    if isinstance(filt, pikepdf.Array):
        if len(filt) != 1:
            return False
        only = filt[0]
        return isinstance(only, pikepdf.Name) and only == pikepdf.Name.DCTDecode
    return False


def _has_signature(pdf: Any) -> bool:
    """Return True iff the PDF has a digital signature flag set."""
    import pikepdf

    root = pdf.Root
    try:
        acroform = root.get(pikepdf.Name.AcroForm)
    except Exception:
        return False
    if acroform is None:
        return False
    try:
        sig_flags = acroform.get(pikepdf.Name.SigFlags)
    except Exception:
        return False
    if sig_flags is None:
        return False
    try:
        return bool(int(sig_flags) & 1)
    except (TypeError, ValueError):
        return False


def _synthetic_zipinfo(objgen: tuple[int, int]) -> ZipInfo:
    """
    Build a ZipInfo whose filename uniquely identifies a PDF stream object.

    The filename has a ``.jpg`` suffix so picopt's PIL-based detector picks
    the bytes up as a JPEG. The object number and generation are encoded
    into the stem so :meth:`Pdf.pack_into` can map an optimized child back
    to its source object on the second pass.

    The 1980-01-01 date_time is the zip epoch and is used purely to keep
    ``ArchiveInfo.mtime()`` from returning None down the call chain.
    """
    obj_num, obj_gen = objgen
    return ZipInfo(
        filename=f"pdf_obj_{obj_num}_{obj_gen}.jpg",
        date_time=(1980, 1, 1, 0, 0, 0),
    )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class Pdf(ContainerHandler):
    """
    PDF container handler.

    The PDF is treated as an "archive" of stream objects in the routing
    layer (``OUTPUT_FILE_FORMAT.archive=True``) so the framework dispatches
    it through the same walk → optimize-children → repack pipeline as
    Zip/Tar/SevenZip. ``CONVERT_CHILDREN`` is forced off: PDF readers do
    not speak WebP, so the global ``--convert-to`` flag must never coerce
    embedded JPEGs into another format.
    """

    OUTPUT_FORMAT_STR: str = "PDF"
    SUFFIXES: tuple[str, ...] = (".pdf",)
    OUTPUT_FILE_FORMAT = FileFormat(OUTPUT_FORMAT_STR, archive=True)
    INPUT_FILE_FORMATS = frozenset({OUTPUT_FILE_FORMAT})
    CONTAINER_TYPE: str = "PDF"
    CONVERT_CHILDREN: bool = False
    PIPELINE: tuple[tuple[Tool, ...], ...] = ((_PIKEPDF_TOOL,),)

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Init PDF state."""
        super().__init__(*args, **kwargs)
        # Stash for round-tripping the input bytes from walk() (called
        # in-process) to pack_into() (called from a multiprocessing worker).
        # Path is the cheap case; raw bytes is the in-archive fallback.
        # Both are picklable; live pikepdf.Pdf objects are not, so we
        # never keep one between calls.
        self._input_path: Path | None = None
        self._input_bytes: bytes | None = None
        # Map synthetic child filename → (obj_num, obj_gen). Built during
        # walk(), consumed during pack_into() to find which object each
        # optimized child came from.
        self._jpeg_objgen_map: dict[str, tuple[int, int]] = {}

    # ------------------------------------------------------------- input I/O

    def _open_input_pdf(self):
        """Open the input PDF, regardless of whether it lives on disk or in a buffer."""
        import pikepdf

        if self._input_path is not None:
            return pikepdf.open(self._input_path)
        if self._input_bytes is not None:
            return pikepdf.open(BytesIO(self._input_bytes))
        # First call: figure out which case we're in.
        if self.path_info.path is not None:
            self._input_path = self.path_info.path
            return pikepdf.open(self._input_path)
        buf: BytesIO | BufferedReader = self.path_info.fp_or_buffer()
        try:
            buf.seek(0)
            self._input_bytes = buf.read()
        finally:
            with suppress(Exception):
                buf.close()
        return pikepdf.open(BytesIO(self._input_bytes))

    # ----------------------------------------------------------------- walk

    def _create_jpeg_path_info(self, objgen: tuple[int, int], data: bytes) -> PathInfo:
        zipinfo = _synthetic_zipinfo(objgen)
        path_info = PathInfo(
            path_info=self.path_info,
            archiveinfo=zipinfo,
            data=data,
            convert=False,
            container_parents=self.path_info.container_path_history(),
        )
        self._jpeg_objgen_map[zipinfo.filename] = objgen
        return path_info

    def _walk_pdf_obj(self, obj, pikepdf) -> PathInfo | None:
        if not isinstance(obj, pikepdf.Stream):
            return None
        try:
            if obj.get(pikepdf.Name.Subtype) != pikepdf.Name.Image:
                return None
            if not _is_dct_filter(obj.get(pikepdf.Name.Filter)):
                return None
            raw = obj.read_raw_bytes()
        except Exception:
            # One weird object should never sink the whole file.
            if self.config.verbose > 1:
                cprint(f"Read error on PDF object {obj}, continuing.", "yellow")
            return None
        if not raw:
            return None
        return self._create_jpeg_path_info(obj.objgen, raw)

    @override
    def walk(self) -> Generator[PathInfo]:
        """
        Yield each embedded JPEG stream as a child PathInfo.

        Non-DCT streams are not yielded — qpdf will recompress them
        structurally during pack_into(), no per-child handler needed.
        """
        self._printer.scan_archive(self.path_info)
        try:
            pdf = self._open_input_pdf()
        except Exception as exc:
            # Encrypted PDF, malformed PDF, or pikepdf import failure.
            # Re-raise so _handle_container's outer try/except converts it
            # into a clean error report for this file.
            msg = f"could not open PDF {self.path_info.full_output_name()}: {exc}"
            raise OSError(msg) from exc

        try:
            if refuse := _has_signature(pdf):
                msg = (
                    f"{self.path_info.full_output_name()}: "
                    "PDF has a digital signature; refusing to modify."
                )
                cprint(msg, "yellow")
            else:
                import pikepdf

                for obj in pdf.objects:
                    if path_info := self._walk_pdf_obj(obj, pikepdf):
                        yield path_info
        except PasswordError:
            refuse = True
            msg = (
                f"{self.path_info.full_output_name()}: "
                "PDF is encrypted; refusing to modify."
            )
            cprint(msg, "yellow")
        finally:
            with suppress(Exception):
                pdf.close()

        # Force the repack pass to run unconditionally. Even a PDF with
        # zero embedded JPEGs benefits from qpdf's Flate level-9 +
        # object-stream + xref-stream rewrite, which is the second source
        # of savings the handoff calls out. The framework's per-file
        # bytes_in vs bytes_out check in _cleanup_after_optimize discards
        # the rewrite cleanly if it grew the file (common for already-
        # optimized PDFs), so flipping this flag is safe.
        self._do_repack = not refuse

        self._walk_finish()

    # ------------------------------------------------------------ packing

    def _apply_optimized_jpeg(self, child, objgen_to_obj, pikepdf) -> int:
        ai = child.archiveinfo
        if ai is None:
            return 0
        objgen = self._jpeg_objgen_map.get(ai.filename())
        if objgen is None:
            return 0
        obj = objgen_to_obj.get(objgen)
        if obj is None:
            return 0
        try:
            original_raw = obj.read_raw_bytes()
            optimized = child.data()
        except Exception:
            cprint(f"Error reading PDF image: {obj}", "red")
            raise
        if not optimized or len(optimized) >= len(original_raw):
            return 0
        try:
            obj.write(optimized, filter=pikepdf.Name.DCTDecode)
        except Exception:
            cprint(f"Error writing optimized PDF image {obj}", "red")
            raise
        return 1

    def _apply_optimized_jpegs(self, pdf: Any) -> int:
        """
        Write each optimized child JPEG back into its source object.

        Returns the number of objects actually mutated. Skips any whose
        optimized bytes are not strictly smaller than the original.
        """
        import pikepdf

        replaced = 0
        # Build a fast lookup of the live objects in this freshly-opened
        # PDF. PDF objgen tuples are stable across opens because they're
        # part of the file's xref table.
        objgen_to_obj: dict[tuple[int, int], Any] = {}
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream):
                objgen_to_obj[obj.objgen] = obj

        for child in self._optimized_contents:
            replaced += self._apply_optimized_jpeg(child, objgen_to_obj, pikepdf)
        return replaced

    @override
    def pack_into(self) -> BytesIO:
        """
        Build the recompressed PDF.

        Reopens the input (the open from walk() was closed deliberately
        because pikepdf objects don't survive multiprocessing pickling),
        applies any smaller-JPEG replacements, then saves through qpdf
        with maximum-compression flags.
        """
        import pikepdf

        pdf = self._open_input_pdf()
        try:
            self._apply_optimized_jpegs(pdf)
            output_buffer = BytesIO()
            pdf.save(
                output_buffer,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                compress_streams=True,
                stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
                recompress_flate=True,
                linearize=False,
            )
        finally:
            with suppress(Exception):
                pdf.close()
        return output_buffer

    # ------------------------------------------------------------ hydration

    @override
    def hydrate_optimized_path_info(
        self: ContainerHandler | Pdf | Any, path_info: PathInfo, report: ReportStats
    ) -> None:
        """
        Pull optimized child bytes back onto the child PathInfo.

        We do not honor child renames here — a synthetic ``pdf_obj_N_G.jpg``
        name is meaningless to anything except our own pack_into lookup, so
        renames cannot bubble up to the PDF.
        """
        if report.data:
            path_info.set_data(report.data)


# ---------------------------------------------------------------------------
# Plugin descriptor
# ---------------------------------------------------------------------------

PLUGIN = Plugin(
    name="PDF",
    handlers=(Pdf,),
    routes=(Route(file_format=Pdf.OUTPUT_FILE_FORMAT, native=Pdf),),
    detector=PdfDetector,
    default_enabled=False,
)
