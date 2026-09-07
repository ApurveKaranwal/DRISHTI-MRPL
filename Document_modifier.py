"""
A deterministic document-modification worker; it deliberately has no LLM.

The supervisor decides WHAT to change (replacement text, new content) and
sends a small list of typed operation dicts. This worker only knows how to
execute that fixed vocabulary of edits - it never interprets natural
language and never decides content itself. Every call produces a NEW output
file; originals are never overwritten.

Changes from v1:
  1. DOCX find_replace now covers tables, headers, and footers (all
     section variants), not just top-level body paragraphs.
  2. DOCX/PPTX find_replace preserves per-run formatting: only the run(s)
     touching the match are rewritten; untouched runs are left alone, and
     the replacement text inherits the formatting of the run where the
     match starts, instead of collapsing the whole paragraph into one run.
  3. PDF find_replace makes a best-effort attempt to match the original
     span's font size (and bold/italic-derived base font) when redrawing
     replacement text, rather than a hardcoded 11pt Helvetica.
  4. PDF rotate_page validates degrees are one of {0, 90, 180, 270}.
  5. XLSX operations validate sheet names and A1-style cell references
     before touching the workbook.
  6. Image insertion validates image_path resolves inside an explicitly
     configured allowed-uploads directory - it will not open an arbitrary
     filesystem path.
  7. Every handler validates the full operation list up front (types,
     required fields, format-specific constraints) before applying any
     operation, so a bad op never leaves a partially-edited file.
  8. Added CSV support (set_cell, add_row) alongside docx/xlsx/pptx/pdf.
"""

from __future__ import annotations

import csv
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf as fitz  # PyMuPDF - PDF text replacement (via redaction), watermarking, rotation.
import openpyxl
from openpyxl.utils import column_index_from_string
from openpyxl.utils.exceptions import IllegalCharacterError
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Inches as PptxInches

DOCX_SUFFIXES = {".docx"}
XLSX_SUFFIXES = {".xlsx"}
PPTX_SUFFIXES = {".pptx"}
PDF_SUFFIXES = {".pdf"}
CSV_SUFFIXES = {".csv"}

VALID_ROTATIONS = {0, 90, 180, 270}
CELL_REF_RE = re.compile(r"^[A-Za-z]{1,3}[1-9][0-9]*$")


class UnsupportedFormatError(RuntimeError):
    pass


class UnsupportedOperationError(RuntimeError):
    pass


class InvalidOperationError(RuntimeError):
    """Raised when an operation dict fails pre-execution validation."""
    pass


class ModificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModifierSettings:
    output_dir: Path = Path("./outputs")
    # insert_image operations must reference a file inside this directory.
    # None disables insert_image entirely (safer default than "allow anything").
    allowed_upload_dir: Path | None = None


REQUIRED_KEYS_BY_OP: dict[str, set[str]] = {
    "find_replace": {"find", "replace"},
    "add_paragraph": {"text"},
    "add_heading": {"text"},
    "insert_image": {"image_path"},
    "set_cell": {"sheet", "cell", "value"},
    "add_row": {"sheet", "values"},
    "add_sheet": {"name"},
    "add_slide": {"title", "body"},
    "add_watermark": {"text"},
    "rotate_page": {"page_number", "degrees"},
}

OPS_BY_FORMAT: dict[str, set[str]] = {
    "docx": {"find_replace", "add_paragraph", "add_heading", "insert_image"},
    "xlsx": {"set_cell", "add_row", "add_sheet"},
    "pptx": {"find_replace", "add_slide"},
    "pdf": {"find_replace", "add_watermark", "rotate_page"},
    "csv": {"set_cell", "add_row"},
}


def _validate_operations(fmt: str, operations: list[dict[str, Any]]) -> None:
    """Type/shape-check every operation before anything is touched on disk."""
    allowed = OPS_BY_FORMAT[fmt]
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            raise InvalidOperationError(f"operation[{i}]: expected a dict, got {type(op).__name__}")
        op_type = op.get("type")
        if op_type not in REQUIRED_KEYS_BY_OP:
            raise InvalidOperationError(f"operation[{i}]: unknown operation type '{op_type}'")
        if op_type not in allowed:
            raise InvalidOperationError(f"operation[{i}]: '{op_type}' is not valid for .{fmt} files")
        missing = set(REQUIRED_KEYS_BY_OP[op_type]) - set(op.keys())
        if fmt == "csv" and "sheet" in missing:
            op["sheet"] = "Sheet1"
            missing.discard("sheet")
        if missing:
            raise InvalidOperationError(
                f"operation[{i}] ('{op_type}'): missing required field(s) {sorted(missing)}"
            )
        if op_type == "rotate_page" and int(op["degrees"]) not in VALID_ROTATIONS:
            raise InvalidOperationError(
                f"operation[{i}]: rotate_page degrees must be one of {sorted(VALID_ROTATIONS)}, "
                f"got {op['degrees']}"
            )
        if op_type in ("set_cell", "add_row") and not str(op["sheet"]).strip():
            raise InvalidOperationError(f"operation[{i}]: 'sheet' must be a non-empty name")
        if op_type == "set_cell" and not CELL_REF_RE.match(str(op["cell"])):
            raise InvalidOperationError(
                f"operation[{i}]: '{op['cell']}' is not a valid A1-style cell reference"
            )


class DocumentModifierWorker:
    """Applies a fixed vocabulary of edits to docx/xlsx/pptx/pdf/csv files."""

    def __init__(self, settings: ModifierSettings | None = None) -> None:
        self.settings = settings or ModifierSettings()
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    def modify(self, file_path: str | Path, operations: list[dict[str, Any]]) -> dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Not a readable file: {path}")
        if not operations:
            raise ValueError("No operations supplied - nothing to modify.")

        suffix = path.suffix.lower()
        fmt = {
            **{s: "docx" for s in DOCX_SUFFIXES},
            **{s: "xlsx" for s in XLSX_SUFFIXES},
            **{s: "pptx" for s in PPTX_SUFFIXES},
            **{s: "pdf" for s in PDF_SUFFIXES},
            **{s: "csv" for s in CSV_SUFFIXES},
        }.get(suffix)
        if fmt is None:
            raise UnsupportedFormatError(
                f"{path.name}: no editor for '{suffix}'. Supported: "
                f"{sorted(DOCX_SUFFIXES | XLSX_SUFFIXES | PPTX_SUFFIXES | PDF_SUFFIXES | CSV_SUFFIXES)}"
            )

        # Validate the *entire* op list up front - a bad op later in the list
        # must never leave an earlier, already-applied op in a half-written file.
        _validate_operations(fmt, operations)
        if fmt == "docx":
            for op in operations:
                if op["type"] == "insert_image":
                    self._validate_image_path(op["image_path"])

        output_path = self.settings.output_dir / f"{path.stem}_{uuid.uuid4().hex[:8]}{suffix}"
        try:
            handler = {
                "docx": self._modify_docx,
                "xlsx": self._modify_xlsx,
                "pptx": self._modify_pptx,
                "pdf": self._modify_pdf,
                "csv": self._modify_csv,
            }[fmt]
            applied = handler(path, output_path, operations)
        except (UnsupportedFormatError, UnsupportedOperationError, InvalidOperationError, ValueError):
            output_path.unlink(missing_ok=True)
            raise
        except Exception as error:
            output_path.unlink(missing_ok=True)
            raise ModificationError(f"Failed to modify {path.name}: {error}") from error

        return {
            "source_name": path.name,
            "output_path": str(output_path),
            "operations_applied": applied,
        }

    def _validate_image_path(self, image_path: str) -> None:
        if self.settings.allowed_upload_dir is None:
            raise InvalidOperationError(
                "insert_image is disabled: no allowed_upload_dir configured on ModifierSettings."
            )
        resolved = Path(image_path).resolve()
        allowed_root = self.settings.allowed_upload_dir.resolve()
        if allowed_root not in resolved.parents and resolved != allowed_root:
            raise InvalidOperationError(
                f"insert_image: '{image_path}' is not inside the allowed uploads directory."
            )
        if not resolved.is_file():
            raise InvalidOperationError(f"insert_image: '{image_path}' does not exist.")

    # ------------------------------------------------------------------ #
    # DOCX handler
    # ------------------------------------------------------------------ #
    def _modify_docx(self, path: Path, output_path: Path, operations: list[dict[str, Any]]) -> list[str]:
        document = Document(str(path))
        applied: list[str] = []

        for op in operations:
            op_type = op["type"]
            if op_type == "find_replace":
                count = self._docx_find_replace_everywhere(document, op["find"], op["replace"])
                applied.append(f"find_replace('{op['find']}' -> '{op['replace']}', {count} matches)")
            elif op_type == "add_paragraph":
                document.add_paragraph(op["text"], style=op.get("style"))
                applied.append(f"add_paragraph('{op['text'][:40]}...')")
            elif op_type == "add_heading":
                document.add_heading(op["text"], level=int(op.get("level", 1)))
                applied.append(f"add_heading('{op['text']}', level={op.get('level', 1)})")
            elif op_type == "insert_image":
                width = op.get("width_inches")
                document.add_picture(op["image_path"], width=Inches(width) if width else None)
                applied.append(f"insert_image('{op['image_path']}')")

        document.save(str(output_path))
        return applied

    def _docx_find_replace_everywhere(self, document: Document, find: str, replace: str) -> int:
        """Replaces in body paragraphs, all tables (incl. nested), and every
        header/footer variant across all sections."""
        count = 0

        def walk_tables(tables):
            nonlocal count
            for table in tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            count += self._replace_in_paragraph(paragraph, find, replace)
                        walk_tables(cell.tables)  # nested tables

        for paragraph in document.paragraphs:
            count += self._replace_in_paragraph(paragraph, find, replace)
        walk_tables(document.tables)

        for section in document.sections:
            for container in (
                section.header, section.footer,
                section.first_page_header, section.first_page_footer,
                section.even_page_header, section.even_page_footer,
            ):
                if container is None:
                    continue
                for paragraph in container.paragraphs:
                    count += self._replace_in_paragraph(paragraph, find, replace)
                walk_tables(container.tables)

        return count

    @staticmethod
    def _replace_in_paragraph(paragraph, find: str, replace: str) -> int:
        """Replaces `find` with `replace` across a paragraph's runs while
        preserving each run's own formatting. Only the run where a match
        *starts* donates its formatting to the inserted replacement text;
        runs with no match are left completely untouched."""
        if not find:
            return 0
        runs = paragraph.runs
        full_text = "".join(r.text for r in runs)
        if find not in full_text:
            return 0

        # char -> owning run index
        run_of_char: list[int] = []
        for i, r in enumerate(runs):
            run_of_char.extend([i] * len(r.text))

        pieces_by_run: dict[int, list[str]] = {i: [] for i in range(len(runs))}
        count = 0
        i = 0
        n = len(find)
        while i < len(full_text):
            if full_text[i:i + n] == find:
                owner = run_of_char[i]
                pieces_by_run[owner].append(replace)
                i += n
                count += 1
            else:
                owner = run_of_char[i]
                pieces_by_run[owner].append(full_text[i])
                i += 1

        for idx, run in enumerate(runs):
            run.text = "".join(pieces_by_run[idx])

        return count

    # ------------------------------------------------------------------ #
    # XLSX handler
    # ------------------------------------------------------------------ #
    def _modify_xlsx(self, path: Path, output_path: Path, operations: list[dict[str, Any]]) -> list[str]:
        workbook = openpyxl.load_workbook(str(path))
        applied: list[str] = []

        for op in operations:
            op_type = op["type"]
            if op_type == "set_cell":
                self._require_sheet(workbook, op["sheet"], must_exist=True)
                self._require_valid_cell(op["sheet"], op["cell"])
                sheet = workbook[op["sheet"]]
                try:
                    sheet[op["cell"]] = op["value"]
                except IllegalCharacterError as e:
                    raise InvalidOperationError(f"set_cell: illegal characters in value: {e}") from e
                applied.append(f"set_cell({op['sheet']}!{op['cell']} = {op['value']!r})")
            elif op_type == "add_row":
                self._require_sheet(workbook, op["sheet"], must_exist=True)
                sheet = workbook[op["sheet"]]
                sheet.append(op["values"])
                applied.append(f"add_row({op['sheet']}, {len(op['values'])} values)")
            elif op_type == "add_sheet":
                if op["name"] in workbook.sheetnames:
                    raise InvalidOperationError(f"add_sheet: sheet '{op['name']}' already exists")
                workbook.create_sheet(title=op["name"])
                applied.append(f"add_sheet('{op['name']}')")

        workbook.save(str(output_path))
        return applied

    @staticmethod
    def _require_sheet(workbook, name: str, must_exist: bool) -> None:
        exists = name in workbook.sheetnames
        if must_exist and not exists:
            raise InvalidOperationError(
                f"sheet '{name}' does not exist. Available sheets: {workbook.sheetnames}"
            )

    @staticmethod
    def _require_valid_cell(sheet_name: str, cell_ref: str) -> None:
        if not CELL_REF_RE.match(cell_ref):
            raise InvalidOperationError(f"'{cell_ref}' is not a valid A1-style cell reference")
        col_letters = re.match(r"[A-Za-z]+", cell_ref).group(0)
        try:
            column_index_from_string(col_letters.upper())
        except ValueError as e:
            raise InvalidOperationError(f"'{cell_ref}': invalid column reference") from e

    # ------------------------------------------------------------------ #
    # PPTX handler
    # ------------------------------------------------------------------ #
    def _modify_pptx(self, path: Path, output_path: Path, operations: list[dict[str, Any]]) -> list[str]:
        presentation = Presentation(str(path))
        applied: list[str] = []

        for op in operations:
            op_type = op["type"]
            if op_type == "find_replace":
                count = self._pptx_find_replace(presentation, op["find"], op["replace"])
                applied.append(f"find_replace('{op['find']}' -> '{op['replace']}', {count} matches)")
            elif op_type == "add_slide":
                self._pptx_add_slide(presentation, op.get("title", ""), op.get("body", ""))
                applied.append(f"add_slide('{op.get('title', '')}')")

        presentation.save(str(output_path))
        return applied

    def _pptx_find_replace(self, presentation: Presentation, find: str, replace: str) -> int:
        count = 0
        for slide in presentation.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        count += self._replace_in_paragraph(paragraph, find, replace)
                if shape.has_table:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            for paragraph in cell.text_frame.paragraphs:
                                count += self._replace_in_paragraph(paragraph, find, replace)
        return count

    @staticmethod
    def _pptx_add_slide(presentation: Presentation, title: str, body: str) -> None:
        layout = presentation.slide_layouts[1]
        slide = presentation.slides.add_slide(layout)
        slide.shapes.title.text = title
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text_frame.text = body

    # ------------------------------------------------------------------ #
    # PDF handler
    # ------------------------------------------------------------------ #
    def _modify_pdf(self, path: Path, output_path: Path, operations: list[dict[str, Any]]) -> list[str]:
        applied: list[str] = []
        with fitz.open(str(path)) as pdf:
            for op in operations:
                op_type = op["type"]
                if op_type == "find_replace":
                    count = self._pdf_find_replace(pdf, op["find"], op["replace"])
                    applied.append(f"find_replace('{op['find']}' -> '{op['replace']}', {count} matches)")
                elif op_type == "add_watermark":
                    self._pdf_add_watermark(pdf, op["text"])
                    applied.append(f"add_watermark('{op['text']}')")
                elif op_type == "rotate_page":
                    page = pdf.load_page(int(op["page_number"]))
                    page.set_rotation(int(op["degrees"]))
                    applied.append(f"rotate_page({op['page_number']}, {op['degrees']} degrees)")
            pdf.save(str(output_path))
        return applied

    @staticmethod
    def _pdf_find_replace(pdf: fitz.Document, find: str, replace: str) -> int:
        count = 0
        for page in pdf:
            matches = page.search_for(find)
            if not matches:
                continue

            # Best-effort: grab font size (and bold/italic-derived base font)
            # for the span each match sits in, BEFORE redaction destroys it.
            span_info = []
            text_dict = page.get_text("dict")
            for rect in matches:
                info = {"size": 11.0, "fontname": "helv"}
                for block in text_dict.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if span_rect.intersects(rect):
                                info["size"] = span.get("size", 11.0)
                                flags = span.get("flags", 0)
                                bold = bool(flags & 2 ** 4)
                                italic = bool(flags & 2 ** 1)
                                if bold and italic:
                                    info["fontname"] = "hebo"  # Helvetica-BoldOblique
                                elif bold:
                                    info["fontname"] = "hebo"  # Helvetica-Bold
                                elif italic:
                                    info["fontname"] = "heit"  # Helvetica-Oblique
                                else:
                                    info["fontname"] = "helv"
                                break
                span_info.append(info)

            for rect in matches:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

            for rect, info in zip(matches, span_info):
                page.insert_text(
                    (rect.x0, rect.y1 - 2),
                    replace,
                    fontsize=info["size"],
                    fontname=info["fontname"],
                )
                # Note: this matches size/weight reasonably well for
                # non-embedded base fonts. Custom embedded fonts still can't
                # be reproduced exactly - PyMuPDF can't re-embed a font it
                # doesn't have a program for.
            count += len(matches)
        return count

    @staticmethod
    def _pdf_add_watermark(pdf: fitz.Document, text: str) -> None:
        for page in pdf:
            rect = page.rect
            center = fitz.Point(rect.width / 2, rect.height / 2)
            rotation_matrix = fitz.Matrix(45)
            page.insert_text(
                (rect.width / 4, rect.height / 2),
                text,
                fontsize=40,
                color=(0.75, 0.75, 0.75),
                morph=(center, rotation_matrix),
                overlay=True,
            )

    # ------------------------------------------------------------------ #
    # CSV handler
    # ------------------------------------------------------------------ #
    def _modify_csv(self, path: Path, output_path: Path, operations: list[dict[str, Any]]) -> list[str]:
        with path.open(newline="", encoding="utf-8") as f:
            rows = [row for row in csv.reader(f)]

        applied: list[str] = []
        for op in operations:
            op_type = op["type"]
            if op_type == "set_cell":
                row_idx, col_idx = self._csv_cell_to_index(op["cell"])
                while len(rows) <= row_idx:
                    rows.append([])
                while len(rows[row_idx]) <= col_idx:
                    rows[row_idx].append("")
                rows[row_idx][col_idx] = str(op["value"])
                applied.append(f"set_cell({op['sheet']}!{op['cell']} = {op['value']!r})")
            elif op_type == "add_row":
                rows.append([str(v) for v in op["values"]])
                applied.append(f"add_row({len(op['values'])} values)")

        with output_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        return applied

    @staticmethod
    def _csv_cell_to_index(cell_ref: str) -> tuple[int, int]:
        """A1-style ref -> (0-indexed row, 0-indexed col). CSV has no
        concept of sheets, so `sheet` is accepted (for symmetry with xlsx
        ops) but ignored."""
        m = CELL_REF_RE.match(cell_ref)
        if not m:
            raise InvalidOperationError(f"'{cell_ref}' is not a valid A1-style cell reference")
        col_letters = re.match(r"[A-Za-z]+", cell_ref).group(0)
        row_digits = cell_ref[len(col_letters):]
        col_idx = column_index_from_string(col_letters.upper()) - 1
        row_idx = int(row_digits) - 1
        return row_idx, col_idx