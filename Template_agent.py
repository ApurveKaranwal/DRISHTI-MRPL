"""MRPL Industrial Deliverables Engine.

Authors formal, print-ready PSU and refinery deliverables from scratch:
1. Official MRPL Internal Approval Notes (.docx) with PSU memorandum styling,
   structured NDT data tables, API standard citations, and multi-tier sign-off blocks.
2. Executive Briefing Presentations (.pptx).
3. Engineering Calculation Sheets (.xlsx).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGBColor

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


@dataclass(frozen=True)
class DeliverablesSettings:
    output_dir: Path = Path(os.getenv("DELIVERABLES_DIR", "./outputs/reports"))


def _set_cell_background(cell, hex_color: str):
    """Sets background shading of a docx table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tc_pr.append(shd)


def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding of a docx table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement('w:tcMar')
    for margin_name, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{margin_name}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tc_mar.append(node)
    tc_pr.append(tc_mar)


class DeliverablesWorker:
    """Generates official MRPL documents, presentations, and calculation workbooks."""

    def __init__(self, settings: DeliverablesSettings | None = None) -> None:
        self.settings = settings or DeliverablesSettings()
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    def author_approval_note(
        self,
        ref_no: str = "MRPL/TS/2026/NOTE-01",
        department: str = "Technical Services",
        subject: str = "Internal Approval Note",
        approving_authority: str = "Chief General Manager (Technical Services)",
        background: str = "Refinery technical inspection and integrity review.",
        findings: str = "Technical evaluation completed in accordance with MRPL procedures.",
        safety_compliance: str = "Compliant with statutory OISD and API standards.",
        financial_impact: str = "Within approved annual operational budget.",
        recommendations: str = "Recommended for technical concurrence and administrative approval.",
        prepared_by: str = "Senior Inspection Engineer",
        inspection_data: list[dict[str, Any]] | None = None,
        cost_breakdown: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Creates a formal MRPL Internal Approval Note (.docx) in standard PSU format."""
        doc = Document()

        # Document Page Setup: 0.75 in margins
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.8)
            section.right_margin = Inches(0.8)

        # ----------------------------------------------------------------- #
        # HEADER BLOCK: Organization & PSU Branding
        # ----------------------------------------------------------------- #
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p.paragraph_format.space_after = Pt(2)
        r1 = title_p.add_run("MANGALORE REFINERY AND PETROCHEMICALS LIMITED")
        r1.font.name = "Arial"
        r1.font.size = Pt(14)
        r1.font.bold = True
        r1.font.color.rgb = RGBColor(0, 51, 102)  # Navy Blue

        sub_p = doc.add_paragraph()
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_p.paragraph_format.space_after = Pt(4)
        r2 = sub_p.add_run("(A Subsidiary of Oil and Natural Gas Corporation Limited - ONGC)\nKuthethoor P.O., Mangalore - 575030, Karnataka")
        r2.font.name = "Arial"
        r2.font.size = Pt(8.5)
        r2.font.color.rgb = RGBColor(90, 90, 90)

        div_p = doc.add_paragraph()
        div_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        div_p.paragraph_format.space_after = Pt(12)
        r3 = div_p.add_run("INTERNAL MEMORANDUM / APPROVAL NOTE")
        r3.font.name = "Arial"
        r3.font.size = Pt(11)
        r3.font.bold = True
        r3.font.underline = True
        r3.font.color.rgb = RGBColor(139, 0, 0)  # Crimson

        # ----------------------------------------------------------------- #
        # METADATA TABLE
        # ----------------------------------------------------------------- #
        meta_table = doc.add_table(rows=4, cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        meta_table.autofit = False

        meta_rows = [
            ("Note Ref. Number:", ref_no),
            ("Department / Unit:", department),
            ("Date:", datetime.now(timezone.utc).strftime("%d %B, %Y")),
            ("Submitting To:", approving_authority),
        ]

        for i, (label, val) in enumerate(meta_rows):
            cell_lbl, cell_val = meta_table.rows[i].cells
            cell_lbl.width = Inches(1.8)
            cell_val.width = Inches(5.0)
            
            p_lbl = cell_lbl.paragraphs[0]
            p_lbl.paragraph_format.space_after = Pt(2)
            run_lbl = p_lbl.add_run(label)
            run_lbl.font.bold = True
            run_lbl.font.size = Pt(9.5)
            
            p_val = cell_val.paragraphs[0]
            p_val.paragraph_format.space_after = Pt(2)
            run_val = p_val.add_run(val)
            run_val.font.size = Pt(9.5)
            
            _set_cell_background(cell_lbl, "F0F4F8")
            _set_cell_margins(cell_lbl, top=60, bottom=60, left=100, right=100)
            _set_cell_margins(cell_val, top=60, bottom=60, left=100, right=100)

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # ----------------------------------------------------------------- #
        # SUBJECT BLOCK
        # ----------------------------------------------------------------- #
        subj_table = doc.add_table(rows=1, cols=1)
        subj_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_subj = subj_table.rows[0].cells[0]
        cell_subj.width = Inches(6.8)
        _set_cell_background(cell_subj, "E8EEF5")
        _set_cell_margins(cell_subj, top=100, bottom=100, left=150, right=150)
        p_subj = cell_subj.paragraphs[0]
        p_subj.paragraph_format.space_after = Pt(0)
        r_subj_lbl = p_subj.add_run("SUBJECT: ")
        r_subj_lbl.font.bold = True
        r_subj_lbl.font.size = Pt(10.5)
        r_subj_lbl.font.color.rgb = RGBColor(0, 51, 102)
        r_subj_val = p_subj.add_run(subject.upper())
        r_subj_val.font.bold = True
        r_subj_val.font.size = Pt(10.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(8)

        # ----------------------------------------------------------------- #
        # HELPER FOR NUMBERED SECTIONS
        # ----------------------------------------------------------------- #
        def add_section(num: str, heading: str, body: str):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            r_num = p.add_run(f"{num}. {heading}\n")
            r_num.font.bold = True
            r_num.font.size = Pt(11)
            r_num.font.color.rgb = RGBColor(0, 51, 102)
            
            p_body = doc.add_paragraph()
            p_body.paragraph_format.space_after = Pt(6)
            p_body.paragraph_format.line_spacing = 1.15
            r_body = p_body.add_run(body)
            r_body.font.size = Pt(10)

        # 1. Background
        add_section("1", "BACKGROUND & OPERATIONAL CONTEXT", background)

        # 2. Inspection Findings
        add_section("2", "TECHNICAL INSPECTION & NDT EVALUATION", findings)

        # Optional NDT Table
        if inspection_data:
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            table_ndt = doc.add_table(rows=len(inspection_data) + 1, cols=6)
            table_ndt.alignment = WD_TABLE_ALIGNMENT.CENTER
            headers = ["Equipment Tag", "Location", "Nominal (mm)", "Measured (mm)", "Min Required (mm)", "Condition"]
            for col_idx, h in enumerate(headers):
                c = table_ndt.rows[0].cells[col_idx]
                _set_cell_background(c, "003366")
                _set_cell_margins(c, top=80, bottom=80, left=100, right=100)
                p = c.paragraphs[0]
                run = p.add_run(h)
                run.font.bold = True
                run.font.size = Pt(8.5)
                run.font.color.rgb = RGBColor(255, 255, 255)

            for row_idx, row in enumerate(inspection_data):
                for col_idx, key in enumerate(["tag", "location", "nominal", "measured", "min_req", "condition"]):
                    c = table_ndt.rows[row_idx + 1].cells[col_idx]
                    val = str(row.get(key, "-"))
                    _set_cell_background(c, "F9FAFC" if row_idx % 2 == 0 else "FFFFFF")
                    _set_cell_margins(c, top=60, bottom=60, left=80, right=80)
                    p = c.paragraphs[0]
                    run = p.add_run(val)
                    run.font.size = Pt(8.5)
                    if key == "condition" and "Critical" in val:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(180, 0, 0)

            doc.add_paragraph().paragraph_format.space_after = Pt(6)

        # 3. Safety & Regulatory Compliance
        add_section("3", "SAFETY & STATUTORY STANDARDS (API 510 / OISD-STD-129)", safety_compliance)

        # 4. Financial Implications
        add_section("4", "FINANCIAL & PROCUREMENT IMPLICATIONS", financial_impact)

        # 5. Recommendations
        add_section("5", "RECOMMENDATIONS FOR ADMINISTRATIVE & FINANCIAL APPROVAL", recommendations)

        # ----------------------------------------------------------------- #
        # SIGN-OFF BLOCK
        # ----------------------------------------------------------------- #
        p_sign = doc.add_paragraph()
        p_sign.paragraph_format.space_before = Pt(20)
        p_sign.paragraph_format.space_after = Pt(4)
        r_sub = p_sign.add_run("Submitted for kind review and formal approval:\n")
        r_sub.font.italic = True
        r_sub.font.size = Pt(9.5)

        sig_table = doc.add_table(rows=2, cols=3)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        sig_roles = [
            ("Prepared By:\n\n\n_______________________\n" + prepared_by, "Technical Services"),
            ("Reviewed By:\n\n\n_______________________\nChief Manager", "Technical Services & Inspection"),
            ("Approved By:\n\n\n_______________________\n" + approving_authority, "Refinery Operations"),
        ]

        for i, (sig_text, dept_text) in enumerate(sig_roles):
            c = sig_table.rows[0].cells[i]
            c.width = Inches(2.26)
            _set_cell_background(c, "F7F9FB")
            _set_cell_margins(c, top=100, bottom=100, left=100, right=100)
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(sig_text)
            r.font.size = Pt(8.5)
            
            p2 = sig_table.rows[1].cells[i].paragraphs[0]
            p2.paragraph_format.space_after = Pt(0)
            r_dept = p2.add_run(dept_text)
            r_dept.font.italic = True
            r_dept.font.size = Pt(7.5)
            r_dept.font.color.rgb = RGBColor(120, 120, 120)

        # Save document
        safe_name = f"MRPL_Approval_Note_{uuid.uuid4().hex[:8]}.docx"
        out_path = self.settings.output_dir / safe_name
        doc.save(str(out_path))

        return {
            "deliverable_type": "docx_approval_note",
            "ref_no": ref_no,
            "subject": subject,
            "file_path": str(out_path.resolve()),
            "file_name": safe_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def author_presentation(
        self,
        title: str,
        subtitle: str,
        slides_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Creates an executive briefing slide deck (.pptx)."""
        prs = Presentation()

        # Title Slide
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        slide.shapes.title.text = title
        slide.placeholders[1].text = f"{subtitle}\nMangalore Refinery and Petrochemicals Limited (MRPL)"

        # Content Slides
        bullet_layout = prs.slide_layouts[1]
        for sdata in slides_data:
            sl = prs.slides.add_slide(bullet_layout)
            sl.shapes.title.text = sdata.get("title", "Technical Briefing")
            tf = sl.placeholders[1].text_frame
            points = sdata.get("points", [])
            for idx, pt in enumerate(points):
                if idx == 0:
                    tf.text = pt
                else:
                    p = tf.add_paragraph()
                    p.text = pt
                    p.level = 0

        safe_name = f"MRPL_Executive_Brief_{uuid.uuid4().hex[:8]}.pptx"
        out_path = self.settings.output_dir / safe_name
        prs.save(str(out_path))

        return {
            "deliverable_type": "pptx_presentation",
            "title": title,
            "slides_count": len(slides_data) + 1,
            "file_path": str(out_path.resolve()),
            "file_name": safe_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def author_calculation_sheet(
        self,
        sheet_title: str,
        parameters: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Creates an engineering calculation workbook (.xlsx)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Engineering Calc"
        ws.views.sheetView[0].showGridLines = True

        # Header Title
        ws.merge_cells("A1:E1")
        top_cell = ws["A1"]
        top_cell.value = f"MRPL TECHNICAL SERVICES — {sheet_title.upper()}"
        top_cell.font = Font(name="Arial", size=13, bold=True, color="FFFFFF")
        top_cell.fill = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
        top_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 32

        # Subheader info
        ws["A2"] = f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Confidential - On Premises Only"
        ws["A2"].font = Font(name="Arial", size=9, italic=True, color="555555")

        # Section 1: Inputs
        row_cursor = 4
        ws.cell(row=row_cursor, column=1, value="1. DESIGN & OPERATING PARAMETERS").font = Font(name="Arial", size=11, bold=True, color="003366")
        row_cursor += 1

        headers_p = ["Parameter Description", "Symbol", "Value", "Unit", "Design Standard / Source"]
        for col_idx, h in enumerate(headers_p, start=1):
            cell = ws.cell(row=row_cursor, column=col_idx, value=h)
            cell.font = Font(name="Arial", size=9.5, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4682B4", end_color="4682B4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        row_cursor += 1

        for p in parameters:
            ws.cell(row=row_cursor, column=1, value=p.get("name", ""))
            ws.cell(row=row_cursor, column=2, value=p.get("symbol", ""))
            ws.cell(row=row_cursor, column=3, value=p.get("value", ""))
            ws.cell(row=row_cursor, column=4, value=p.get("unit", ""))
            ws.cell(row=row_cursor, column=5, value=p.get("source", "Field Measured"))
            row_cursor += 1

        # Section 2: Calculated Outputs
        row_cursor += 2
        ws.cell(row=row_cursor, column=1, value="2. COMPUTED RESULTS & THRESHOLD VERIFICATION").font = Font(name="Arial", size=11, bold=True, color="003366")
        row_cursor += 1

        headers_r = ["Output Metric", "Computed Value", "Permissible Limit", "Status", "Remarks"]
        for col_idx, h in enumerate(headers_r, start=1):
            cell = ws.cell(row=row_cursor, column=col_idx, value=h)
            cell.font = Font(name="Arial", size=9.5, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2E8B57", end_color="2E8B57", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        row_cursor += 1

        for r in results:
            ws.cell(row=row_cursor, column=1, value=r.get("metric", ""))
            ws.cell(row=row_cursor, column=2, value=r.get("value", ""))
            ws.cell(row=row_cursor, column=3, value=r.get("limit", ""))
            status_cell = ws.cell(row=row_cursor, column=4, value=r.get("status", "VERIFIED"))
            status = r.get("status", "").upper()
            if "CRITICAL" in status or "FAIL" in status:
                status_cell.font = Font(name="Arial", size=9.5, bold=True, color="9C0006")
                status_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            else:
                status_cell.font = Font(name="Arial", size=9.5, bold=True, color="006100")
                status_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            ws.cell(row=row_cursor, column=5, value=r.get("remarks", ""))
            row_cursor += 1

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        safe_name = f"MRPL_Calc_Sheet_{uuid.uuid4().hex[:8]}.xlsx"
        out_path = self.settings.output_dir / safe_name
        wb.save(str(out_path))

        return {
            "deliverable_type": "xlsx_calc_sheet",
            "sheet_title": sheet_title,
            "file_path": str(out_path.resolve()),
            "file_name": safe_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
