"""MRPL Sovereign AI Workbench - All-Agent Verification Test Suite.

Runs tests on all 6 deterministic agents directly (standalone) and via the
SupervisorAgent (natural language orchestration) without requiring the web frontend.

Usage:
    python tests/test_all_agents.py           # Runs full suite (direct + supervisor)
    python tests/test_all_agents.py --direct  # Runs only direct worker unit tests
    python tests/test_all_agents.py --nlp     # Runs only supervisor NL query tests
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure project root is in python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Data_agent import DataAnalysisWorker
from Document_agent import RetrievalWorker
from Vision_agent import VisionWorker
from Sandbox_agent import CodeSandboxWorker
from Template_agent import DeliverablesWorker
from Document_modifier import DocumentModifierWorker
from Supervisor_agent import SupervisorAgent


def test_data_analysis():
    print("\n" + "-" * 55)
    print("Testing Agent 1: DataAnalysisWorker (Data_agent.py)")
    print("-" * 55)
    w = DataAnalysisWorker()
    tables = w.list_tables()
    print(f"  [OK] DuckDB connected. Loaded tables: {len(tables)}")
    for t in tables:
        print(f"       - {t['table_name']} ({t['row_count']} rows, {t['column_count']} cols)")
    
    query = "SELECT crude_name, api_gravity, sulfur_wt_pct FROM real_crude_oil_assays ORDER BY api_gravity DESC LIMIT 3"
    res = w.query(query)
    print(f"  [OK] Query executed: {query}")
    print(f"       Returned {res['row_count_returned']} rows:")
    for row in res['rows']:
        print(f"       * {row}")
    assert res['row_count_returned'] == 3, "Expected 3 rows"
    print("  >>> DataAnalysisWorker: ALL CHECKS PASSED")


def test_document_retrieval():
    print("\n" + "-" * 55)
    print("Testing Agent 2: RetrievalWorker (Document_agent.py)")
    print("-" * 55)
    w = RetrievalWorker()
    files = w.list_files()
    print(f"  [OK] SQLite/RAG store loaded. Total documents indexed: {len(files)}")
    for f in files:
        print(f"       - {f.get('source_name')} ({f.get('media_type')})")
    
    query = "API 510 statutory inspection frequency pressure vessel"
    results = w.search(query, limit=2)
    print(f"  [OK] Search query: '{query}'")
    print(f"       Matches found: {len(results)}")
    for i, match in enumerate(results, 1):
        print(f"       Match {i}: {match.get('source_name')} (score: {match.get('score', 0):.2f})")
        print(f"       Snippet: {match.get('text', '')[:120].strip()}...")
    assert len(results) > 0, "Expected at least 1 search match"
    print("  >>> RetrievalWorker: ALL CHECKS PASSED")


def test_code_sandbox():
    print("\n" + "-" * 55)
    print("Testing Agent 3: CodeSandboxWorker (Sandbox_agent.py)")
    print("-" * 55)
    w = CodeSandboxWorker()
    engineering_script = '''
# Darcy-Weisbach Pressure Drop Calculation
import math

length_m = 250.0        # 250m pipe run
diameter_m = 0.2032     # 8-inch Sch 40 (0.2032m ID)
flow_rate_m3h = 180.0   # 180 m3/h
density_kg_m3 = 845.0   # Crude density
viscosity_pa_s = 0.008  # 8 cP

area = math.pi * (diameter_m / 2)**2
velocity = (flow_rate_m3h / 3600.0) / area
reynolds = (density_kg_m3 * velocity * diameter_m) / viscosity_pa_s
f_friction = 0.3164 / (reynolds ** 0.25) if reynolds > 4000 else 64.0 / reynolds
delta_p_pa = f_friction * (length_m / diameter_m) * (density_kg_m3 * velocity**2 / 2)
delta_p_bar = delta_p_pa / 1e5

print(f"Velocity: {velocity:.2f} m/s")
print(f"Reynolds Number: {reynolds:.0f}")
print(f"Pressure Drop: {delta_p_bar:.3f} bar")
'''
    res = w.execute_code(engineering_script)
    print(f"  [OK] Sandbox executed in {res.get('duration_seconds', 0):.3f}s (Exit code: {res.get('returncode')})")
    print(f"       STDOUT:\n{res.get('stdout', '').strip()}")
    assert res.get('success') is True, "Sandbox execution failed"
    assert "Pressure Drop:" in res.get('stdout', ''), "Expected pressure drop in stdout"
    print("  >>> CodeSandboxWorker: ALL CHECKS PASSED")


def test_deliverables_author():
    print("\n" + "-" * 55)
    print("Testing Agent 4: DeliverablesWorker (Template_agent.py)")
    print("-" * 55)
    w = DeliverablesWorker()
    
    # 1. DOCX Note
    note_res = w.author_approval_note(
        subject="Emergency Weld Overlay Cladding for Column CDU-Col-04",
        department="Technical Services & Inspection",
        approving_authority="Executive Director (Refinery Operations)",
        background="UT thickness survey revealed localized corrosion below 6.0mm minimum retirement thickness.",
        findings="Critical thickness deficit of -1.82mm observed at CML 01-C.",
        safety_compliance="Statutory OISD-STD-129 and API 510 Section 7 compliance requires shutdown intervention.",
        financial_impact="Estimated cladding cost: INR 45 Lakhs. Spares available in stock.",
        recommendations="Grant immediate shutdown concurrence for Inconel 625 weld overlay cladding."
    )
    note_path = Path(note_res["file_path"])
    print(f"  [OK] Approval Note (.docx) generated: {note_path.name} ({note_path.stat().st_size} bytes)")
    assert note_path.exists(), "DOCX file was not created"

    # 2. XLSX Calculation Sheet
    calc_res = w.author_calculation_sheet(
        sheet_title="CDU-Col-04 Remaining Life & Retirement Assessment",
        parameters=[
            {"name": "Original Thickness", "value": 14.0, "unit": "mm"},
            {"name": "Minimum Retirement (t_min)", "value": 6.0, "unit": "mm"},
            {"name": "Actual Measured Thickness", "value": 4.18, "unit": "mm"},
            {"name": "Operating Interval", "value": 3.0, "unit": "years"}
        ],
        results=[
            {"name": "Current Deficit", "value": -1.82, "unit": "mm"},
            {"name": "Corrosion Rate", "value": 0.873, "unit": "mm/year"},
            {"name": "Remaining Life", "value": "EXPIRED (Negative)", "unit": "years"}
        ]
    )
    calc_path = Path(calc_res["file_path"])
    print(f"  [OK] Calculation Sheet (.xlsx) generated: {calc_path.name} ({calc_path.stat().st_size} bytes)")
    assert calc_path.exists(), "XLSX file was not created"

    # 3. PPTX Presentation
    pres_res = w.author_presentation(
        title="MRPL Phase-1 CDU Turnaround Briefing",
        subtitle="Asset Integrity & Statutory Compliance Review",
        slides_data=[
            {
                "title": "CDU-Col-04 Ultrasonic Survey Summary",
                "bullets": [
                    "Survey conducted 14-JAN-2026 by NDT Inspection Division",
                    "Elev +4.2m North/South/East/West grid readings < 6.0 mm t_min",
                    "High TAN sour crude blend processing identified as primary driver"
                ]
            },
            {
                "title": "Corrective Action & Procurement Status",
                "bullets": [
                    "In-situ Inconel 625 weld overlay cladding recommended",
                    "Spares catalog verified: Alloy cladding consumables on hand",
                    "Expected shutdown duration: 72 hours"
                ]
            }
        ]
    )
    pres_path = Path(pres_res["file_path"])
    print(f"  [OK] Presentation (.pptx) generated: {pres_path.name} ({pres_path.stat().st_size} bytes)")
    assert pres_path.exists(), "PPTX file was not created"
    print("  >>> DeliverablesWorker: ALL CHECKS PASSED")


def test_document_modifier():
    print("\n" + "-" * 55)
    print("Testing Agent 5: DocumentModifierWorker (Document_modifier.py)")
    print("-" * 55)
    w = DocumentModifierWorker()
    
    # 1. Modify CSV
    test_csv = ROOT / "outputs" / "sandbox" / "test_pipe_specs.csv"
    test_csv.parent.mkdir(parents=True, exist_ok=True)
    test_csv.write_text("Line,Tag,Nominal_mm,Status\nL-101,CDU-Feed,14.0,Active\nL-102,VDU-Bottom,16.0,Active\n")
    
    res = w.modify(
        str(test_csv),
        [{"type": "set_cell", "cell": "D2", "value": "CRITICAL_ALERT"}]
    )
    out_csv = Path(res["output_path"])
    print(f"  [OK] CSV modified: {out_csv.name} ({out_csv.stat().st_size} bytes)")
    print(f"       Operations applied: {res['operations_applied']}")
    assert "CRITICAL_ALERT" in out_csv.read_text(), "CSV modification value not found"
    
    # 2. Modify DOCX
    test_docx = ROOT / "outputs" / "sandbox" / "test_memo.docx"
    from docx import Document
    doc = Document()
    doc.add_paragraph("Original Subject: Preliminary Review")
    doc.save(str(test_docx))
    
    res_docx = w.modify(
        str(test_docx),
        [{"type": "find_replace", "find": "Preliminary Review", "replace": "FINAL APPROVED SPECIFICATION"}]
    )
    out_docx = Path(res_docx["output_path"])
    print(f"  [OK] DOCX modified: {out_docx.name}")
    print(f"       Operations applied: {res_docx['operations_applied']}")
    assert out_docx.exists(), "Modified DOCX not found"
    print("  >>> DocumentModifierWorker: ALL CHECKS PASSED")


def test_vision():
    print("\n" + "-" * 55)
    print("Testing Agent 6: VisionWorker (Vision_agent.py)")
    print("-" * 55)
    w = VisionWorker()
    img_path = ROOT / "data" / "mrpl_cdu_inspection_report.png"
    if not img_path.exists():
        print("  [SKIP] Sample image not found.")
        return

    res = w.process_image(str(img_path))
    print(f"  [OK] Processed image: {res.get('source')}")
    print(f"       Source type: {res.get('source_type')}")
    print(f"       Combined text preview ({len(res.get('combined_text', ''))} chars):")
    snippet = res.get('combined_text', '').strip()[:180].replace('\n', ' ')
    print(f"       \"{snippet}...\"")
    assert res.get("combined_text"), "Vision processing returned empty text"
    print("  >>> VisionWorker: ALL CHECKS PASSED")


def test_supervisor_nlp_queries():
    print("\n" + "=" * 65)
    print("TESTING SUPERVISOR AGENT NATURAL LANGUAGE ROUTING & SYNTHESIS")
    print("=" * 65)
    supervisor = SupervisorAgent()
    
    queries = [
        {
            "name": "SQL Data Analysis (DuckDB)",
            "query": "What is the average API gravity of imported crudes in the assay dataset?",
            "files": [],
            "expected_worker": "data_analysis"
        },
        {
            "name": "SOP & Standards Retrieval (RAG)",
            "query": "What are the API 510 statutory inspection requirements for pressure vessels in refineries?",
            "files": [],
            "expected_worker": "document_retrieval"
        },
        {
            "name": "Engineering Calculation (Sandbox)",
            "query": "Calculate the Darcy-Weisbach pressure drop for 100 meters of pipe with fluid velocity 2.5 m/s and density 850 kg/m3",
            "files": [],
            "expected_worker": "code_sandbox"
        },
        {
            "name": "Ultrasonic Scan PDF (Vision)",
            "query": "Summarize findings",
            "files": ["data/real_cdu_ultrasonic_thickness_scan.pdf"],
            "expected_worker": "vision"
        }
    ]

    for item in queries:
        print(f"\n[Test Case] {item['name']}")
        print(f"  Query: \"{item['query']}\"")
        if item['files']:
            print(f"  Files: {item['files']}")
        
        t0 = time.time()
        res = supervisor.handle(item['query'], item['files'])
        duration = time.time() - t0
        
        plan = res.get("plan", {})
        actions = plan.get("actions", [])
        workers_used = [a.get("worker") for a in actions]
        routing = res.get("routing", {})
        
        print(f"  Execution Time: {duration:.1f}s")
        print(f"  Routing Mode:   {routing.get('mode')} ({routing.get('model_id')})")
        print(f"  Workers Chosen: {workers_used}")
        print(f"  Answer Snippet: {res.get('answer', '')[:160].strip().replace(chr(10), ' ')}...")
        
        assert item["expected_worker"] in workers_used, f"Expected {item['expected_worker']} in plan, got {workers_used}"
        print(f"  >>> {item['name']}: SUCCESS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test all MRPL Sovereign AI Agents")
    parser.add_argument("--direct", action="store_true", help="Run only direct agent unit tests")
    parser.add_argument("--nlp", action="store_true", help="Run only supervisor natural language tests")
    args = parser.parse_args()

    run_all = not (args.direct or args.nlp)

    print("=" * 65)
    print("  MRPL SOVEREIGN AI WORKBENCH - COMPLETE AGENT TEST SUITE")
    print("=" * 65)

    if run_all or args.direct:
        test_data_analysis()
        test_document_retrieval()
        test_code_sandbox()
        test_deliverables_author()
        test_document_modifier()
        test_vision()
        print("\n" + "=" * 65)
        print("  ALL 6 WORKER AGENTS PASSED DIRECT VERIFICATION!")
        print("=" * 65)

    if run_all or args.nlp:
        test_supervisor_nlp_queries()
        print("\n" + "=" * 65)
        print("  ALL SUPERVISOR NATURAL LANGUAGE ORCHESTRATIONS PASSED!")
        print("=" * 65)
