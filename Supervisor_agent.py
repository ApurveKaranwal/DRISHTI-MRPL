"""MRPL Sovereign AI Workbench — Supervisor Agent.

Orchestrates six deterministic local workers:

1. document_retrieval: indexes & searches document evidence (MRPL SOPs, API standards).
2. data_analysis: loads CSV/TSV/XLS/XLSX into DuckDB and runs read-only SQL.
3. vision: runs Tesseract OCR and local VLM on images and scanned PDF pages.
4. document_modifier: creates new edited versions of existing DOCX/XLSX/PPTX/PDF/CSV.
5. code_sandbox: executes Python code in an isolated local sandbox with stdout/plot capture.
6. template_author: authors formal MRPL Approval Notes (.docx), presentations (.pptx),
   and calculation sheets (.xlsx).

Features:
- Fixed local Supervisor LLM: qwen3:8b.
- Air-Gap Sovereign Network Telemetry.
- Self-healing plan validation with SQL normalization.
- Deterministic fallback routing if the Supervisor LLM is unavailable.
- Deterministic fallback response generation if final LLM synthesis fails.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from Data_agent import DataAnalysisWorker, DuplicateFileError
from Document_agent import RetrievalWorker

from Document_modifier import (
    DocumentModifierWorker,
    OPS_BY_FORMAT,
    REQUIRED_KEYS_BY_OP,
    DOCX_SUFFIXES,
    XLSX_SUFFIXES,
    PPTX_SUFFIXES,
    PDF_SUFFIXES,
    CSV_SUFFIXES,
)

from Vision_agent import VisionWorker
from Sandbox_agent import CodeSandboxWorker
from Template_agent import DeliverablesWorker
from Sovereign_monitor import SovereignNetworkAuditor


_SUFFIX_TO_MODIFIER_FORMAT: dict[str, str] = {
    **{s: "docx" for s in DOCX_SUFFIXES},
    **{s: "xlsx" for s in XLSX_SUFFIXES},
    **{s: "pptx" for s in PPTX_SUFFIXES},
    **{s: "pdf" for s in PDF_SUFFIXES},
    **{s: "csv" for s in CSV_SUFFIXES},
}


# ---------------------------------------------------------------------------
# PLANNER CONTEXT
# ---------------------------------------------------------------------------

AGENT_CONTEXT = """
You supervise six deterministic local workers for
Mangalore Refinery and Petrochemicals Limited (MRPL).

Your job is to understand the user's request, select the minimum number
of workers required, and create an execution plan.

Workers are deterministic tools and are the source of truth for:

- retrieved evidence
- structured-data results
- calculations
- visual extraction
- document modifications
- generated deliverables

Do not perform calculations or invent factual results yourself.

AVAILABLE WORKERS:

1. document_retrieval
---------------------
Searches and indexes internal MRPL documents such as:
- SOPs
- manuals
- procedures
- API standards
- technical references

Returns relevant source chunks/evidence, NOT a final answer.

Use it when:
- The user needs information from internal documents.
- The query asks about procedures, standards, specifications,
  operating limits, maintenance practices, or technical guidance.
- Evidence from MRPL documentation is required.

Do NOT use document_retrieval for structured-data calculations
when data_analysis can answer the question.


2. data_analysis
----------------
Loads CSV/TSV/XLS/XLSX files into DuckDB and executes read-only SQL.

This is the PRIMARY worker for structured/tabular data.

Use it for:
- SELECT/filtering
- SUM
- AVG
- MIN
- MAX
- COUNT
- GROUP BY
- HAVING
- sorting
- LIMIT
- joins between structured tables
- basic SQL statistics and aggregations
- retrieving rows or columns
- schema inspection
- describing tables

IMPORTANT WORKER-SELECTION RULE:

If a requested calculation can naturally be expressed as SQL
over structured/tabular data, PREFER data_analysis.

Do NOT use code_sandbox simply because the query contains mathematics
or arithmetic.

Examples:
"What is the average pressure?"
→ data_analysis

"Find average pressure by section."
→ data_analysis

"What is the maximum temperature?"
→ data_analysis

"Calculate total production for each unit."
→ data_analysis

"Count the number of failed inspections."
→ data_analysis

"Show the average flow rate for each plant section."
→ data_analysis

"Find the minimum and maximum pressure."
→ data_analysis

Only use READ-ONLY SQL.

Never generate:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE
- COPY
- ATTACH
- INSTALL
- other mutating or external SQL operations


3. vision
---------
Uses Tesseract OCR and a local VLM to process explicitly supplied
images or scanned PDF pages.

Use it when:
- An image is supplied by the user.
- A scanned PDF requires OCR/visual extraction.
- Information exists primarily in diagrams, P&IDs,
  inspection sheets, visual tables, handwritten material,
  or other visual content.

OCR is used for text extraction.

VLM is used for:
- visual interpretation
- relationships
- trends
- diagram understanding

Do NOT invoke vision when no image or scan file has been explicitly supplied.


4. document_modifier
--------------------
Creates a NEW edited version of an existing:
- DOCX
- XLSX
- PPTX
- PDF
- CSV

It accepts only predefined typed operations.

Use it when the user asks to:
- edit an existing document
- modify spreadsheet contents
- change presentation content
- update/replace/add/remove supported document elements

Do NOT use it to create a completely new formal deliverable from scratch.


5. code_sandbox
---------------
Executes Python locally in a controlled subprocess with:
- timeout protection
- AST-based security checks
- stdout/stderr capture
- artifact/plot detection

This is the PRIMARY worker for CUSTOM computation and
engineering/numerical logic that is not naturally expressed as SQL.

Use it for:
- engineering equations
- hydraulic calculations
- numerical methods
- iterative calculations
- simulations
- custom mathematical models
- custom algorithms
- Python-based transformations
- matplotlib/custom plots
- calculations requiring multiple computational steps
  that are awkward or unsuitable for SQL

IMPORTANT:

Do NOT use code_sandbox merely because a query contains:
- arithmetic
- averages
- sums
- minimums
- maximums
- counts
- grouping

If those operations can be performed using SQL over structured data,
use data_analysis instead.

Use:

    structured data + normal SQL operation
    → data_analysis

Use:

    custom engineering/numerical computation
    → code_sandbox


Examples:

"Find average pressure for each section."
→ data_analysis

"Find total production for each unit."
→ data_analysis

"Calculate pressure drop using Darcy-Weisbach."
→ code_sandbox

"Perform an iterative hydraulic calculation."
→ code_sandbox

"Run a numerical simulation of the pipeline."
→ code_sandbox

"Generate a custom engineering plot."
→ code_sandbox


IMPORTANT COMBINED CASE:

If a request requires both structured-data processing
AND custom engineering computation, use both workers in sequence.

Example:

"Find the average flow rate for each section and then
use those values to calculate pressure drop."

Correct plan:

1. data_analysis
   → SQL AVG(...) GROUP BY section

2. code_sandbox
   → use the resulting values for the engineering calculation

Do NOT replace the first step with Python.

Do NOT replace the second step with SQL if the calculation
requires custom numerical/engineering logic.


6. template_author
------------------
Generates NEW formal MRPL deliverables from scratch.

Supported actions:

- author_approval_note
  → formal MRPL Internal Approval Note (.docx)

- author_presentation
  → executive briefing presentation (.pptx)

- author_calculation_sheet
  → engineering calculation workbook (.xlsx)

Use when the user explicitly requests a NEW formal deliverable.

Do NOT use document_modifier for creating a completely new
deliverable from scratch.


GENERAL WORKER-SELECTION PRINCIPLES:

1. Select the smallest useful plan.

2. Use data_analysis whenever structured data can answer
   the question through SQL.

3. Use code_sandbox only when custom Python computation,
   engineering logic, numerical methods, simulations,
   algorithms, or custom plotting are actually required.

4. Do not duplicate computational work across
   data_analysis and code_sandbox.

5. If one worker can completely answer the computational
   part, do not invoke another computational worker.

6. Complex requests may require multiple workers in sequence.

7. The output of an earlier worker may provide input/context
   needed by a later worker.

8. Retrieval workers retrieve evidence; they do not invent answers.

9. Deterministic workers are the source of truth.

10. Never invent worker results.

11. The final response must be based only on supplied worker results.


COMMON DECISION BOUNDARY:

Structured/tabular data
+
Standard SQL operation
→ DATA_ANALYSIS

Custom engineering/math/numerical computation
→ CODE_SANDBOX

Internal document knowledge/evidence
→ DOCUMENT_RETRIEVAL

Image/scanned visual information
→ VISION

Editing an existing file
→ DOCUMENT_MODIFIER

Creating a new formal MRPL deliverable
→ TEMPLATE_AUTHOR


EXAMPLES:

Example 1:
User:
"What is the average pressure in each plant section?"

Plan:
data_analysis → SQL AVG + GROUP BY


Example 2:
User:
"Calculate the pressure drop using Darcy-Weisbach."

Plan:
code_sandbox → engineering calculation


Example 3:
User:
"Using the inspection spreadsheet, find the average pressure
for each section and calculate the pressure drop using
the Darcy-Weisbach equation."

Plan:
1. data_analysis → retrieve/aggregate structured data
2. code_sandbox → perform engineering calculation


Example 4:
User:
"What does the MRPL SOP say about the maximum allowable pressure?"

Plan:
document_retrieval → search relevant SOP/standard


Example 5:
User:
"Edit this Excel file and remove all rows where pressure is below 5 bar."

Plan:
document_modifier → modify the supplied spreadsheet


Example 6:
User:
"Create an MRPL approval note from these findings."

Plan:
template_author → author_approval_note

Never invent worker outputs.

Select the smallest useful plan.

Use a worker only when needed.
"""


# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SupervisorSettings:
    scratch_dir: Path = Path(
        os.getenv("SUPERVISOR_DATA_DIR", "./data/supervisor")
    )
    report_dir: Path = Path(
        os.getenv("SUPERVISOR_REPORT_DIR", "./outputs/reports")
    )


# ---------------------------------------------------------------------------
# SUPERVISOR
# ---------------------------------------------------------------------------

class SupervisorAgent:
    """Routes user requests to local workers and synthesizes grounded results."""

    LLM_MODEL = "qwen3:8b"
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    def __init__(
        self,
        settings: SupervisorSettings | None = None,
        document_worker: RetrievalWorker | None = None,
        data_worker: DataAnalysisWorker | None = None,
        vision_worker: VisionWorker | None = None,
        modifier_worker: DocumentModifierWorker | None = None,
        sandbox_worker: CodeSandboxWorker | None = None,
        template_worker: DeliverablesWorker | None = None,
        auditor: SovereignNetworkAuditor | None = None,
        **kwargs: Any,
    ) -> None:

        self.settings = settings or SupervisorSettings()

        self.settings.scratch_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.settings.report_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.document_worker = document_worker
        self.data_worker = data_worker
        self.vision_worker = vision_worker
        self.modifier_worker = modifier_worker
        self.sandbox_worker = sandbox_worker
        self.template_worker = template_worker

        self.auditor = auditor or SovereignNetworkAuditor(
            self.settings.report_dir
        )

    # -----------------------------------------------------------------------
    # LOCAL LLM
    # -----------------------------------------------------------------------

    def _llm_chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> str:
        """Call the local Supervisor LLM through Ollama HTTP API."""

        payload: dict[str, Any] = {
            "model": self.LLM_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_ctx": 8192,
            },
        }

        if json_mode:
            payload["format"] = "json"

        timeout_sec = float(os.getenv("LLM_TIMEOUT", "180.0"))
        response = requests.post(
            f"{self.OLLAMA_URL}/api/chat",
            json=payload,
            timeout=timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        msg = data.get("message", {})
        content = msg.get("content", "")
        if not content and "thinking" in msg:
            content = msg.get("thinking", "")
        return content

    def _llm_available(self) -> bool:
        """
        Lightweight local health check.

        Pings the local Ollama service directly via loopback HTTP.
        Returns False when the local Ollama service cannot be reached.
        """

        try:
            resp = requests.get(f"{self.OLLAMA_URL}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # LAZY WORKER INITIALIZATION
    # -----------------------------------------------------------------------

    def _document(self) -> RetrievalWorker:
        if self.document_worker is None:
            self.document_worker = RetrievalWorker()
        return self.document_worker

    def _data(self) -> DataAnalysisWorker:
        if self.data_worker is None:
            self.data_worker = DataAnalysisWorker()
        return self.data_worker

    def _vision(self) -> VisionWorker:
        if self.vision_worker is None:
            self.vision_worker = VisionWorker()
        return self.vision_worker

    def _modifier(self) -> DocumentModifierWorker:
        if self.modifier_worker is None:
            self.modifier_worker = DocumentModifierWorker()
        return self.modifier_worker

    def _sandbox(self) -> CodeSandboxWorker:
        if self.sandbox_worker is None:
            self.sandbox_worker = CodeSandboxWorker()
        return self.sandbox_worker

    def _template(self) -> DeliverablesWorker:
        if self.template_worker is None:
            self.template_worker = DeliverablesWorker()
        return self.template_worker

    # -----------------------------------------------------------------------
    # DATA CONTEXT
    # -----------------------------------------------------------------------

    def _known_tables_context(self) -> str:
        try:
            tables = self._data().list_tables()
            if not tables:
                return "No tables are currently loaded in data_analysis."

            lines = []

            for t in tables:
                tname = t["table_name"]

                try:
                    col_info = self._data().conn.execute(
                        f'PRAGMA table_info("{tname}")'
                    ).fetchall()

                    col_names = [r[1] for r in col_info]
                    cols_str = ", ".join(col_names)

                except Exception:
                    cols_str = f"{t['column_count']} cols"

                lines.append(
                    f'- "{tname}" ({t["row_count"]} rows): [{cols_str}]'
                )

            return (
                "Tables and exact column names loaded in data_analysis "
                "(use these EXACT table and column names in SQL):\n"
                + "\n".join(lines)
            )
        except Exception:
            return "No tables are currently accessible in data_analysis."

    # -----------------------------------------------------------------------
    # DOCUMENT MODIFIER CONTEXT
    # -----------------------------------------------------------------------

    def _modifier_schema_context(self) -> str:
        lines = []

        for fmt in sorted(OPS_BY_FORMAT):
            for op_type in sorted(OPS_BY_FORMAT[fmt]):
                required = sorted(
                    REQUIRED_KEYS_BY_OP[op_type]
                )

                lines.append(
                    f'- .{fmt} file, "type": "{op_type}" '
                    f"— required fields: {required}"
                )

        return (
            "document_modifier operation types "
            '(use ONLY these "type" values, with '
            "EXACTLY these required fields present "
            "on every operation object):\n"
            + "\n".join(lines)
        )

    # -----------------------------------------------------------------------
    # PLANNING
    # -----------------------------------------------------------------------

    def plan(
        self,
        request: str,
        files: list[str] | None = None,
        *,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        """
        Generate and validate a JSON execution plan using qwen3:8b.

        If the local LLM is unavailable or fails repeatedly, a deterministic
        fallback planner is used automatically.
        """

        self.auditor.log_event(
            "PLANNING_DISPATCH",
            "localhost",
            f"Using fixed Supervisor LLM '{self.LLM_MODEL}'"
        )

        # Check local Ollama health first: if offline, bypass to deterministic keyword fallback planner
        if not self._llm_available():
            self.auditor.log_event(
                "PLANNING_FALLBACK",
                "localhost",
                f"Local LLM is offline or unreachable at {self.OLLAMA_URL}. Using deterministic keyword fallback planner."
            )
            return self._generate_fallback_plan(
                request,
                files or []
            )

        base_prompt = f"""
{self._known_tables_context()}

{self._modifier_schema_context()}

CRITICAL PLANNING RULES:

1. If the user asks an operational question or root-cause
   diagnostic (e.g., about temperatures, pressures, alerts),
   use 'document_retrieval' with action 'search' to find
   relevant procedures/standards, or leave 'actions': []
   to answer directly.

2. If the user asks for a calculation over structured/tabular
   data that can naturally be expressed using SQL, use
   'data_analysis'.

3. Do NOT use 'code_sandbox' for simple SQL aggregations such
   as AVG, SUM, MIN, MAX, COUNT, GROUP BY, filtering, sorting,
   or joins.

4. Use 'code_sandbox' for custom engineering calculations,
   numerical methods, simulations, algorithms, or custom
   Python/plot generation.

5. If both structured-data processing and custom engineering
   computation are required, use multiple actions in sequence:
   data_analysis first, then code_sandbox.

6. ONLY invoke 'data_analysis' with 'query' if you provide a
   valid read-only SQL query in 'sql' (e.g. SELECT ...)
   over known tables.

7. NEVER put natural language inside 'sql'.

8. ONLY invoke 'vision' if an image or scan file is explicitly supplied.
   For PDF scans, use action 'process_scanned_pdf'. For images (.png, .jpg), use action 'process_image'.

9. Select the smallest useful plan.

10. Do not invent worker outputs.

Return JSON only, with this exact shape:

{{
  "actions": [
    {{
      "worker":
        "document_retrieval|data_analysis|vision|document_modifier|code_sandbox|template_author",
      "action":
        "search|ingest|query|schema|describe|process_image|process_scanned_pdf|modify|execute_code|author_approval_note|author_presentation|author_calculation_sheet",
      "file": "optional path",
      "query": "optional text",
      "sql": "optional read-only SQL",
      "operations": ["optional modifier ops"],
      "code": "optional python code string",
      "note_data": {{
        "ref_no": "str",
        "department": "str",
        "subject": "str",
        "approving_authority": "str",
        "background": "str",
        "findings": "str",
        "safety_compliance": "str",
        "financial_impact": "str",
        "recommendations": "str"
      }}
    }}
  ],
  "reply_goal": "short description"
}}

User request: {request}

Files explicitly supplied: {files or []}
"""

        messages = [
            {
                "role": "system",
                "content":
                    "You are a careful task planner for MRPL. "
                    + AGENT_CONTEXT,
            },
            {
                "role": "user",
                "content": base_prompt,
            },
        ]

        last_error: Exception | None = None

        for attempt in range(max_attempts):

            try:
                raw = self._llm_chat(
                    messages,
                    json_mode=False,
                    max_tokens=1500,
                    temperature=0.1,
                )

            except Exception as error:
                last_error = error

                self.auditor.log_event(
                    "LLM_FAILURE",
                    "localhost",
                    (
                        f"Supervisor planning LLM '{self.LLM_MODEL}' "
                        f"failed: {error}. "
                        "Switching to deterministic fallback."
                    )
                )

                return self._generate_fallback_plan(
                    request,
                    files or []
                )

            try:
                # Strip reasoning tags such as <think>...</think>
                cleaned_raw = re.sub(
                    r"<think>.*?(?:</think>|$)",
                    "",
                    raw,
                    flags=re.DOTALL
                ).strip()

                # Strip markdown code fences if present
                cleaned_raw = re.sub(r"^```(?:json)?\s*", "", cleaned_raw, flags=re.IGNORECASE)
                cleaned_raw = re.sub(r"\s*```$", "", cleaned_raw)

                # Extract the outer JSON object if the model added text.
                first_brace = cleaned_raw.find("{")
                last_brace = cleaned_raw.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    raw_json = cleaned_raw[first_brace:last_brace + 1]
                else:
                    fb_raw = raw.find("{")
                    lb_raw = raw.rfind("}")
                    if fb_raw != -1 and lb_raw != -1 and lb_raw > fb_raw:
                        raw_json = raw[fb_raw:lb_raw + 1]
                    else:
                        raw_json = cleaned_raw

                plan = json.loads(raw_json)

                self._validate_plan(plan)

                self._validate_plan_files(
                    plan,
                    files or []
                )

                self._validate_modify_operations(plan)

                return plan

            except (json.JSONDecodeError, ValueError) as error:
                last_error = error

                messages.append(
                    {
                        "role": "assistant",
                        "content": raw
                    }
                )

                messages.append(
                    {
                        "role": "user",
                        "content":
                            f"JSON was invalid: {error}. "
                            "Return corrected JSON only."
                    }
                )

        self.auditor.log_event(
            "PLANNING_FALLBACK",
            "localhost",
            (
                f"Supervisor planning exhausted {max_attempts} attempts. "
                f"Last error: {last_error}. "
                "Using deterministic fallback."
            )
        )

        return self._generate_fallback_plan(
            request,
            files or []
        )

    # -----------------------------------------------------------------------
    # DETERMINISTIC FALLBACK PLAN
    # -----------------------------------------------------------------------

    def _generate_fallback_plan(
        self,
        request: str,
        files: list[str],
    ) -> dict[str, Any]:
        """
        Deterministic backup dispatcher.

        This is used only when the Supervisor LLM cannot produce a valid
        plan or cannot be reached.

        It intentionally uses conservative routing rules and can select
        more than one worker.
        """

        q = request.lower().strip()

        actions: list[dict[str, Any]] = []
        seen_routes: set[tuple[str, str]] = set()

        def add_action(action: dict[str, Any]) -> None:
            key = (
                str(action.get("worker")),
                str(action.get("action")),
            )

            if key not in seen_routes:
                actions.append(action)
                seen_routes.add(key)

        # ---------------------------------------------------------------
        # FILE CATEGORIZATION
        # ---------------------------------------------------------------

        image_files = [
            f for f in files
            if Path(f).suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp",
                ".tiff",
                ".webp",
            }
        ]

        structured_files = [
            f for f in files
            if Path(f).suffix.lower() in {
                ".csv",
                ".tsv",
                ".xlsx",
                ".xls",
            }
        ]

        document_files = [
            f for f in files
            if Path(f).suffix.lower() in {
                ".pdf",
                ".docx",
                ".txt",
            }
        ]

        editable_files = [
            f for f in files
            if Path(f).suffix.lower() in _SUFFIX_TO_MODIFIER_FORMAT
        ]

        # ---------------------------------------------------------------
        # KEYWORD GROUPS
        # ---------------------------------------------------------------

        data_keywords = {
            "calculate",
            "average",
            "avg",
            "mean",
            "sum",
            "total",
            "minimum",
            "maximum",
            "max",
            "min",
            "count",
            "how many",
            "group by",
            "grouped",
            "trend",
            "table",
            "row",
            "column",
            "data",
            "dataset",
            "statistics",
            "statistical",
            "schema",
            "describe",
            "filter",
            "sort",
            "assay",
            "assays",
            "crude",
            "crudes",
            "gravity",
            "api_gravity",
            "api gravity",
            "density",
            "sulfur",
            "yield",
        }

        engineering_keywords = {
            "darcy",
            "pressure drop",
            "hydraulic",
            "simulation",
            "simulate",
            "numerical",
            "iterative",
            "iteration",
            "equation",
            "engineering calculation",
            "engineering computation",
            "model",
            "plot",
            "graph",
            "numerical method",
            "heat transfer",
            "mass balance",
            "energy balance",
        }

        document_keywords = {
            "sop",
            "standard",
            "procedure",
            "manual",
            "according to",
            "according",
            "operating limit",
            "allowable",
            "specification",
            "specifications",
            "maintenance",
            "shutdown",
            "startup",
            "safety",
            "api standard",
            "api spec",
            "api 510",
            "api 570",
            "api 650",
            "api 653",
            "api rp",
            "technical guidance",
            "technical reference",
            "document",
        }

        vision_keywords = {
            "image",
            "photo",
            "picture",
            "diagram",
            "p&id",
            "pid",
            "drawing",
            "visual",
            "inspection sheet",
            "handwritten",
            "chart",
            "figure",
            "scanned",
            "scan",
        }

        modifier_keywords = {
            "edit",
            "modify",
            "change",
            "update",
            "replace",
            "remove",
            "delete rows",
            "add rows",
            "insert",
            "rename",
            "format",
            "revise",
        }

        approval_keywords = {
            "approval note",
            "approval notes",
            "internal approval",
            "approval memo",
            "approval memorandum",
        }

        presentation_keywords = {
            "presentation",
            "powerpoint",
            "ppt",
            "pptx",
            "slides",
            "briefing",
            "executive briefing",
        }

        calculation_sheet_keywords = {
            "calculation sheet",
            "calculation workbook",
            "engineering workbook",
            "calculation excel",
        }

        # ---------------------------------------------------------------
        # VISION ROUTING
        # ---------------------------------------------------------------

        # Route PDF files to vision for OCR + VLM extraction
        pdf_files = [
            f for f in files
            if Path(f).suffix.lower() == ".pdf"
        ]

        if pdf_files:
            add_action(
                {
                    "worker": "vision",
                    "action": "process_scanned_pdf",
                    "file": pdf_files[0],
                }
            )

        if image_files:
            add_action(
                {
                    "worker": "vision",
                    "action": "process_image",
                    "file": image_files[0],
                }
            )

        elif any(keyword in q for keyword in vision_keywords):
            # Only route to vision when an explicitly supplied image exists.
            # This prevents the fallback from inventing a visual input.
            if image_files:
                add_action(
                    {
                        "worker": "vision",
                        "action": "process_image",
                        "file": image_files[0],
                    }
                )

        # ---------------------------------------------------------------
        # STRUCTURED DATA ROUTING
        # ---------------------------------------------------------------

        structured_requested = (
            bool(structured_files)
            or any(keyword in q for keyword in data_keywords)
        )

        if structured_requested:
            if structured_files:
                # For fallback mode with supplied file, describe the file
                add_action(
                    {
                        "worker": "data_analysis",
                        "action": "describe",
                        "file": structured_files[0],
                    }
                )
            else:
                # No file explicitly supplied: route against pre-loaded DuckDB tables
                try:
                    known_tables = [t["table_name"] for t in self._data().list_tables()]
                except Exception:
                    known_tables = []

                target_table = None
                if any(k in q for k in ["assay", "crude", "gravity", "api_gravity", "api gravity", "brent", "arab", "maya"]):
                    if "real_crude_oil_assays" in known_tables:
                        target_table = "real_crude_oil_assays"
                elif any(k in q for k in ["monthly", "indigenous", "imported", "processing", "throughput"]):
                    if "ppac_mrpl_monthly_crude_processing" in known_tables:
                        target_table = "ppac_mrpl_monthly_crude_processing"
                elif any(k in q for k in ["slate", "production", "petroleum", "lpg", "diesel", "naphtha"]):
                    if "ppac_mrpl_petroleum_production_slate" in known_tables:
                        target_table = "ppac_mrpl_petroleum_production_slate"
                elif any(k in q for k in ["benchmark", "psu", "nelson", "ioc", "bpcl", "hpcl"]):
                    if "ppac_psu_refineries_benchmark" in known_tables:
                        target_table = "ppac_psu_refineries_benchmark"
                elif any(k in q for k in ["schedule", "pipe", "asme", "thickness", "wall"]):
                    if "asme_pipe_schedules_astm_a106" in known_tables:
                        target_table = "asme_pipe_schedules_astm_a106"
                elif any(k in q for k in ["spare", "spares", "catalog", "equipment"]):
                    if "refinery_equipment_spares_catalog" in known_tables:
                        target_table = "refinery_equipment_spares_catalog"
                elif known_tables:
                    target_table = known_tables[0]

                if target_table == "real_crude_oil_assays" and any(k in q for k in ["average", "avg", "mean"]) and any(k in q for k in ["api", "gravity"]):
                    add_action(
                        {
                            "worker": "data_analysis",
                            "action": "query",
                            "sql": "SELECT AVG(api_gravity) as avg_api_gravity FROM real_crude_oil_assays",
                            "table_name": "real_crude_oil_assays",
                        }
                    )
                elif target_table:
                    add_action(
                        {
                            "worker": "data_analysis",
                            "action": "describe",
                            "table_name": target_table,
                        }
                    )

        # If there are structured files and the user asks for engineering
        # computation, data_analysis comes before code_sandbox.
        if (
            structured_files
            and any(keyword in q for keyword in engineering_keywords)
            and not any(a.get("worker") == "data_analysis" for a in actions)
        ):
            add_action(
                {
                    "worker": "data_analysis",
                    "action": "describe",
                    "file": structured_files[0],
                }
            )

        # ---------------------------------------------------------------
        # DOCUMENT RETRIEVAL ROUTING
        # ---------------------------------------------------------------

        document_requested = (
            bool(document_files)
            or any(keyword in q for keyword in document_keywords)
        )

        if document_requested and (bool(document_files) or not actions):
            add_action(
                {
                    "worker": "document_retrieval",
                    "action": "search",
                    "query": request[:500],
                }
            )

        # ---------------------------------------------------------------
        # CUSTOM ENGINEERING / CODE ROUTING
        # ---------------------------------------------------------------

        if any(keyword in q for keyword in engineering_keywords):

            # Do not generate arbitrary Python code from rules.
            # The fallback only routes to the worker when explicitly asked.
            add_action(
                {
                    "worker": "code_sandbox",
                    "action": "execute_code",
                    "code": (
                        "# Supervisor LLM unavailable.\n"
                        "# No generated engineering code was executed.\n"
                        "# The request requires custom computation and "
                        "must be handled explicitly by the application.\n"
                        "print('Custom engineering computation requires "
                        "LLM-generated or user-supplied code.')"
                    ),
                }
            )

        # ---------------------------------------------------------------
        # DOCUMENT MODIFIER ROUTING
        # ---------------------------------------------------------------

        if (
            editable_files
            and any(keyword in q for keyword in modifier_keywords)
        ):
            add_action(
                {
                    "worker": "document_modifier",
                    "action": "modify",
                    "file": editable_files[0],
                    "operations": [],
                }
            )

        # ---------------------------------------------------------------
        # TEMPLATE AUTHOR ROUTING
        # ---------------------------------------------------------------

        if any(keyword in q for keyword in approval_keywords):
            add_action(
                {
                    "worker": "template_author",
                    "action": "author_approval_note",
                    "note_data": {
                        "ref_no": "",
                        "department": "MRPL",
                        "subject": request[:120],
                        "approving_authority": "",
                        "background": "",
                        "findings": "",
                        "safety_compliance": "",
                        "financial_impact": "",
                        "recommendations": "",
                    },
                }
            )

        elif any(keyword in q for keyword in presentation_keywords):
            add_action(
                {
                    "worker": "template_author",
                    "action": "author_presentation",
                    "title": request[:100] or "MRPL Briefing",
                    "subtitle": "Technical Services",
                    "slides_data": [],
                }
            )

        elif any(keyword in q for keyword in calculation_sheet_keywords):
            add_action(
                {
                    "worker": "template_author",
                    "action": "author_calculation_sheet",
                    "sheet_title": request[:100]
                    or "Engineering Calculation",
                    "parameters": [],
                    "results": [],
                }
            )

        # ---------------------------------------------------------------
        # PDF SCAN ROUTING
        # ---------------------------------------------------------------

        # We cannot safely assume every PDF is scanned.
        # Document retrieval remains the safe generic route.
        if document_files:
            for file_path in document_files:
                if Path(file_path).suffix.lower() == ".pdf":
                    if any(keyword in q for keyword in vision_keywords):
                        add_action(
                            {
                                "worker": "vision",
                                "action": "process_scanned_pdf",
                                "file": file_path,
                            }
                        )

        # ---------------------------------------------------------------
        # FINAL CONSERVATIVE FALLBACK
        # ---------------------------------------------------------------

        if not actions:

            if files:
                # Generic supplied-file case.
                first_file = files[0]
                suffix = Path(first_file).suffix.lower()

                if suffix in {
                    ".csv",
                    ".tsv",
                    ".xlsx",
                    ".xls",
                }:
                    add_action(
                        {
                            "worker": "data_analysis",
                            "action": "describe",
                            "file": first_file,
                        }
                    )

                elif suffix in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".bmp",
                    ".tiff",
                    ".webp",
                }:
                    add_action(
                        {
                            "worker": "vision",
                            "action": "process_image",
                            "file": first_file,
                        }
                    )

                elif suffix == ".pdf":
                    add_action(
                        {
                            "worker": "vision",
                            "action": "process_scanned_pdf",
                            "file": first_file,
                        }
                    )

                else:
                    add_action(
                        {
                            "worker": "document_retrieval",
                            "action": "search",
                            "query": request[:500],
                        }
                    )

            else:
                add_action(
                    {
                        "worker": "document_retrieval",
                        "action": "search",
                        "query": request[:500],
                    }
                )

        return {
            "actions": actions,
            "reply_goal": (
                "Deterministic fallback execution for: "
                f"{request[:120]}"
            ),
            "fallback_mode": True,
            "fallback_reason": (
                "Supervisor LLM unavailable or unable to produce "
                "a valid execution plan."
            ),
        }

    # -----------------------------------------------------------------------
    # FILE VALIDATION
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_plan_files(
        plan: dict[str, Any],
        files: list[str],
    ) -> None:

        allowed = set(files)

        file_requiring_actions = {
            ("document_retrieval", "ingest"),
            ("data_analysis", "ingest"),
            ("data_analysis", "query"),
            ("vision", "process_image"),
            ("vision", "process_scanned_pdf"),
            ("document_modifier", "modify"),
        }

        for action in plan.get("actions", []):

            worker = action.get("worker")
            name = action.get("action")
            file_path = action.get("file")

            if file_path:

                if (
                    file_path in allowed
                    or Path(file_path).is_file()
                    or str(file_path).startswith("data/")
                ):
                    continue

                if (Path("data") / str(file_path)).is_file():
                    action["file"] = str(
                        Path("data") / str(file_path)
                    )
                    continue

            if (
                worker,
                name
            ) in file_requiring_actions and file_path and file_path not in allowed:

                if worker == "data_analysis":
                    action["worker"] = "document_retrieval"
                    action["action"] = "search"
                    action["query"] = (
                        action.get("query")
                        or f"MRPL {name} data"
                    )
                    action.pop("file", None)
                    action.pop("sql", None)

                else:
                    action["file"] = None

    # -----------------------------------------------------------------------
    # MODIFIER VALIDATION
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_modify_operations(
        plan: dict[str, Any]
    ) -> None:

        for index, action in enumerate(
            plan.get("actions", [])
        ):

            if (
                action.get("worker")
                != "document_modifier"
                or action.get("action")
                != "modify"
            ):
                continue

            file_path = action.get("file")
            operations = action.get("operations")

            if not isinstance(operations, list) or not operations:
                raise ValueError(
                    f"actions[{index}]: "
                    "document_modifier.modify requires "
                    "non-empty 'operations'."
                )

            suffix = Path(
                str(file_path)
            ).suffix.lower()

            fmt = _SUFFIX_TO_MODIFIER_FORMAT.get(suffix)

            if fmt is None:
                raise ValueError(
                    f"actions[{index}]: "
                    f"unsupported format '{suffix}'."
                )

            allowed_ops = OPS_BY_FORMAT[fmt]

            for op_index, op in enumerate(operations):

                if not isinstance(op, dict):
                    raise ValueError(
                        f"actions[{index}].operations[{op_index}] "
                        "must be a dict."
                    )

                op_type = op.get("type")

                if (
                    op_type not in REQUIRED_KEYS_BY_OP
                    or op_type not in allowed_ops
                ):
                    raise ValueError(
                        f"actions[{index}].operations[{op_index}]: "
                        f"invalid op '{op_type}'."
                    )

                missing = (
                    REQUIRED_KEYS_BY_OP[op_type]
                    - op.keys()
                )

                if missing:
                    raise ValueError(
                        f"actions[{index}].operations[{op_index}]: "
                        f"missing fields {sorted(missing)}"
                    )

    # -----------------------------------------------------------------------
    # PLAN VALIDATION
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_plan(plan: Any) -> None:

        if (
            not isinstance(plan, dict)
            or not isinstance(plan.get("actions"), list)
        ):
            raise ValueError(
                "Plan must be an object containing an actions list."
            )

        allowed: dict[str, set[str]] = {
            "document_retrieval": {
                "search",
                "ingest",
            },

            "data_analysis": {
                "ingest",
                "query",
                "schema",
                "describe",
            },

            "vision": {
                "process_image",
                "process_scanned_pdf",
            },

            "document_modifier": {
                "modify",
            },

            "code_sandbox": {
                "execute_code",
            },

            "template_author": {
                "author_approval_note",
                "author_presentation",
                "author_calculation_sheet",
            },
        }

        valid_actions = []

        for index, action in enumerate(
            plan["actions"]
        ):

            if not isinstance(action, dict):
                continue

            worker = action.get("worker")
            name = action.get("action")

            if (
                worker not in allowed
                or name not in allowed[worker]
            ):
                continue

            if name == "query":

                sql = str(
                    action.get("sql", "")
                ).strip()

                if (
                    not sql.upper().startswith(
                        ("SELECT", "WITH")
                    )
                    or ";" in sql.rstrip(";")
                ):
                    action["worker"] = "document_retrieval"
                    action["action"] = "search"
                    action["query"] = (
                        action.get("query")
                        or sql
                        or "MRPL process operations"
                    )
                    action.pop("sql", None)

            valid_actions.append(action)

        plan["actions"] = valid_actions

    # -----------------------------------------------------------------------
    # TABLE RESOLUTION
    # -----------------------------------------------------------------------

    def _resolve_table_name(
        self,
        data: DataAnalysisWorker,
        file_path: str,
    ) -> str:

        try:
            ingest_result = data.ingest(
                file_path
            )

            return ingest_result["tables"][0]["table_name"]

        except DuplicateFileError:

            source_name = Path(
                file_path
            ).name

            for table in data.list_tables():

                if (
                    table["source_name"]
                    == source_name
                ):
                    return table["table_name"]

            raise

    # -----------------------------------------------------------------------
    # SQL TABLE REWRITE
    # -----------------------------------------------------------------------

    def _rewrite_sql_table_reference(
        self,
        sql: str,
        file_path: str,
        table_name: str,
    ) -> str:

        stem = Path(
            file_path
        ).stem

        pattern = re.compile(
            re.escape(stem)
            + r"(?:\.\w+)?"
        )

        return pattern.sub(
            table_name,
            sql
        )

    # -----------------------------------------------------------------------
    # UNKNOWN TABLE REWRITE
    # -----------------------------------------------------------------------

    def _rewrite_unknown_table_references(
        self,
        sql: str,
        data: DataAnalysisWorker,
    ) -> str:

        known = data.list_tables()

        if not known:
            return sql

        known_names = {
            t["table_name"]
            for t in known
        }

        referenced = set(
            re.findall(
                r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
                sql,
                flags=re.IGNORECASE
            )
        )

        for guess in referenced - known_names:

            candidates = {
                t["table_name"]
                for t in known
                if (
                    t["table_name"].startswith(guess)
                    or Path(
                        t["source_name"]
                    ).stem == guess
                )
            }

            if len(candidates) == 1:

                real_name = next(
                    iter(candidates)
                )

                sql = re.sub(
                    rf"\b{re.escape(guess)}\b",
                    real_name,
                    sql
                )

        return sql

    # -----------------------------------------------------------------------
    # SQL RESERVED WORDS
    # -----------------------------------------------------------------------

    _SQL_RESERVED = {
        "select",
        "from",
        "where",
        "group",
        "by",
        "order",
        "having",
        "limit",
        "offset",
        "as",
        "and",
        "or",
        "not",
        "sum",
        "avg",
        "count",
        "min",
        "max",
        "distinct",
        "case",
        "when",
        "then",
        "else",
        "end",
        "on",
        "join",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "asc",
        "desc",
        "null",
        "is",
        "in",
        "like",
        "between",
        "with",
        "union",
        "all",
        "extract",
        "date",
        "month",
        "year",
        "day",
        "cast",
        "round",
        "over",
        "partition",
        "coalesce",
        "nullif",
        "true",
        "false",
    }

    # -----------------------------------------------------------------------
    # UNKNOWN COLUMN REWRITE
    # -----------------------------------------------------------------------

    def _rewrite_unknown_columns(
        self,
        sql: str,
        table_name: str,
        data: DataAnalysisWorker,
    ) -> str:

        try:
            real_columns = {
                c["name"]
                for c in data.schema(
                    table_name
                )["columns"]
            }

        except ValueError:
            return sql

        tokens = set(
            re.findall(
                r"\b[A-Za-z_][A-Za-z0-9_]*\b",
                sql
            )
        )

        guesses = {
            token
            for token in tokens
            if (
                token not in real_columns
                and token.lower() not in self._SQL_RESERVED
                and token != table_name
            )
        }

        for guess in guesses:

            candidates = {
                c
                for c in real_columns
                if (
                    c.startswith(guess)
                    or guess in c
                )
            }

            if len(candidates) == 1:

                real_name = next(
                    iter(candidates)
                )

                sql = re.sub(
                    rf"\b{re.escape(guess)}\b",
                    real_name,
                    sql
                )

        return sql

    # -----------------------------------------------------------------------
    # EXECUTION
    # -----------------------------------------------------------------------

    def execute(
        self,
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Executes a validated plan across the local workers."""

        self._validate_plan(plan)

        results: list[dict[str, Any]] = []

        for action in plan["actions"]:

            worker = action["worker"]
            name = action["action"]
            file_path = action.get("file")

            self.auditor.log_event(
                "WORKER_EXECUTE",
                "localhost",
                f"Invoking {worker}.{name}"
            )

            try:

                # -----------------------------------------------------------
                # DOCUMENT RETRIEVAL
                # -----------------------------------------------------------

                if worker == "document_retrieval":

                    doc = self._document()

                    result = (
                        doc.search(
                            action.get("query", "")
                        )
                        if name == "search"
                        else doc.ingest(file_path)
                    )

                # -----------------------------------------------------------
                # DATA ANALYSIS
                # -----------------------------------------------------------

                elif worker == "data_analysis":

                    data = self._data()

                    if (
                        name == "query"
                        and file_path
                    ):

                        table_name = (
                            self._resolve_table_name(
                                data,
                                file_path
                            )
                        )

                        sql = (
                            self._rewrite_sql_table_reference(
                                action["sql"],
                                file_path,
                                table_name
                            )
                        )

                        sql = (
                            self._rewrite_unknown_columns(
                                sql,
                                table_name,
                                data
                            )
                        )

                        result = data.query(sql)

                    elif name == "query":

                        sql = (
                            self._rewrite_unknown_table_references(
                                action["sql"],
                                data
                            )
                        )

                        referenced_tables = set(
                            re.findall(
                                r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
                                sql,
                                flags=re.IGNORECASE
                            )
                        )

                        known_table_names = {
                            t["table_name"]
                            for t in data.list_tables()
                        }

                        for referenced_table in (
                            referenced_tables
                            & known_table_names
                        ):

                            sql = (
                                self._rewrite_unknown_columns(
                                    sql,
                                    referenced_table,
                                    data
                                )
                            )

                        result = data.query(sql)

                    else:

                        target_table = (
                            action.get("table_name")
                            or (self._resolve_table_name(data, file_path) if file_path else None)
                            or (data.list_tables()[0]["table_name"] if data.list_tables() else "real_crude_oil_assays")
                        )

                        result = {
                            "ingest":
                                lambda:
                                    data.ingest(file_path),

                            "schema":
                                lambda:
                                    data.schema(
                                        target_table
                                    ),

                            "describe":
                                lambda:
                                    data.describe(
                                        target_table
                                    ),
                        }[name]()

                # -----------------------------------------------------------
                # VISION
                # -----------------------------------------------------------

                elif worker == "vision":

                    vision = self._vision()
                    suffix = Path(file_path).suffix.lower() if file_path else ""

                    if suffix == ".pdf" or name == "process_scanned_pdf":
                        result = vision.process_scanned_pdf(file_path)
                    else:
                        result = vision.process_image(file_path)

                # -----------------------------------------------------------
                # DOCUMENT MODIFIER
                # -----------------------------------------------------------

                elif worker == "document_modifier":

                    result = (
                        self._modifier().modify(
                            file_path,
                            action["operations"]
                        )
                    )

                # -----------------------------------------------------------
                # CODE SANDBOX
                # -----------------------------------------------------------

                elif worker == "code_sandbox":

                    code_str = action.get(
                        "code",
                        ""
                    )

                    result = (
                        self._sandbox().execute_code(
                            code_str
                        )
                    )

                # -----------------------------------------------------------
                # TEMPLATE AUTHOR
                # -----------------------------------------------------------

                elif worker == "template_author":

                    templ = self._template()

                    if name == "author_approval_note":

                        note_data = action.get(
                            "note_data",
                            {}
                        )

                        result = (
                            templ.author_approval_note(
                                **note_data
                            )
                        )

                    elif name == "author_presentation":

                        result = (
                            templ.author_presentation(
                                action.get(
                                    "title",
                                    "MRPL Briefing"
                                ),
                                action.get(
                                    "subtitle",
                                    "Technical Services"
                                ),
                                action.get(
                                    "slides_data",
                                    []
                                ),
                            )
                        )

                    else:

                        result = (
                            templ.author_calculation_sheet(
                                action.get(
                                    "sheet_title",
                                    "Engineering Calculation"
                                ),
                                action.get(
                                    "parameters",
                                    []
                                ),
                                action.get(
                                    "results",
                                    []
                                ),
                            )
                        )

                else:

                    result = {
                        "status": "unsupported"
                    }

                results.append(
                    {
                        "worker": worker,
                        "action": name,
                        "result": result,
                    }
                )

            except Exception as err:

                results.append(
                    {
                        "worker": worker,
                        "action": name,
                        "result": {
                            "success": False,
                            "error": str(err),
                        },
                    }
                )

        return results

    # -----------------------------------------------------------------------
    # DETERMINISTIC FALLBACK RESPONSE
    # -----------------------------------------------------------------------

    def _build_fallback_response(
        self,
        request: str,
        results: list[dict[str, Any]],
    ) -> str:
        """
        Builds a deterministic response when final LLM synthesis fails.

        This never invents facts. It exposes the actual worker results and
        clearly identifies failures.
        """

        lines: list[str] = []

        lines.append(
            "Supervisor LLM is currently unavailable. "
            "The request was processed using deterministic local workers."
        )

        lines.append("")
        lines.append(f"Request: {request}")

        if not results:
            lines.append("")
            lines.append(
                "No worker results were produced."
            )
            return "\n".join(lines)

        for index, item in enumerate(results, start=1):

            worker = item.get(
                "worker",
                "unknown"
            )

            action = item.get(
                "action",
                "unknown"
            )

            result = item.get(
                "result"
            )

            lines.append("")
            lines.append(
                f"### [Worker {index}] {worker}.{action}"
            )

            if isinstance(result, dict) and (result.get("success") is False or "error" in result):
                lines.append(
                    f"**Status:** FAILED — `{result.get('error', 'Unknown error')}`"
                )
            elif worker == "document_retrieval" and isinstance(result, list):
                lines.append("**Retrieved Evidence Passages:**\n")
                for c_idx, chunk in enumerate(result[:3], 1):
                    if isinstance(chunk, dict) and "text" in chunk:
                        src = chunk.get("source_name", "Document")
                        sec = chunk.get("chunk_index", "")
                        txt = chunk.get("text", "").strip().replace("\n", " ")
                        if len(txt) > 220:
                            txt = txt[:220] + "..."
                        lines.append(f"> **[{c_idx}] `{src}` (Sec {sec}):** {txt}\n")
                    else:
                        lines.append(f"- {chunk}")
            elif worker == "data_analysis" and isinstance(result, list):
                lines.append("| Column | Type | Min | Max | Non-Null % |")
                lines.append("| --- | --- | --- | --- | --- |")
                for col in result[:8]:
                    if isinstance(col, dict):
                        cn = col.get("column_name", "")
                        ct = col.get("column_type", "")
                        cmin = str(col.get("min", "-"))[:12]
                        cmax = str(col.get("max", "-"))[:12]
                        null_pct = col.get("null_percentage", 0)
                        lines.append(f"| `{cn}` | {ct} | {cmin} | {cmax} | {100 - null_pct:.0f}% |")
                if len(result) > 8:
                    lines.append(f"\n*(Showing 8 of {len(result)} columns)*")
            elif worker == "data_analysis" and isinstance(result, dict) and "rows" in result:
                cols = result.get("columns", [])
                rows = result.get("rows", [])
                if cols and rows:
                    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
                    lines.append("| " + " | ".join("---" for _ in cols) + " |")
                    for r in rows[:8]:
                        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
                    if len(rows) > 8:
                        lines.append(f"\n*(Showing 8 of {len(rows)} records)*")
                else:
                    lines.append(f"Query returned {result.get('row_count_returned', 0)} rows.")
            elif worker == "code_sandbox" and isinstance(result, dict):
                stdout = result.get("stdout", "").strip()
                stderr = result.get("stderr", "").strip()
                if stdout:
                    lines.append(f"```text\n{stdout[:400]}\n```")
                if stderr:
                    lines.append(f"\n*Diagnostic stderr:* `{stderr[:200]}`")
            elif worker == "template_author" and isinstance(result, dict):
                fn = result.get("file_name", "Deliverable")
                fp = result.get("file_path", "")
                lines.append(f"Generated deliverable **`{fn}`** saved at `{fp}`.")
            elif isinstance(result, (dict, list)):
                try:
                    formatted = json.dumps(result, indent=2, ensure_ascii=False, default=str)
                    if len(formatted) > 500:
                        formatted = formatted[:500] + "\n  ... (truncated for brevity)"
                    lines.append(f"```json\n{formatted}\n```")
                except Exception:
                    lines.append(f"`{str(result)[:200]}`")
            else:
                lines.append(f"{result}")

        lines.append("")
        lines.append(
            "This response contains only deterministic worker output "
            "and does not contain LLM-generated conclusions."
        )

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # RESPONSE GENERATION
    # -----------------------------------------------------------------------

    def respond(
        self,
        request: str,
        results: list[dict[str, Any]],
    ) -> str:
        """
        Synthesizes grounded worker results using qwen3:8b.

        If the LLM is unavailable, returns a deterministic worker-result
        response instead of failing the complete request.
        """

        evidence = json.dumps(
            results,
            default=str,
            ensure_ascii=False
        )

        # Check local Ollama health: if offline, return direct deterministic worker outputs
        if not self._llm_available():
            self.auditor.log_event(
                "RESPONSE_FALLBACK",
                "localhost",
                f"Local LLM is offline or unreachable at {self.OLLAMA_URL}. Building direct structured worker-result response."
            )
            return self._build_fallback_response(
                request,
                results
            )

        try:

            resp = self._llm_chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful, authoritative chemical & refinery engineering assistant for Mangalore Refinery and Petrochemicals Limited (MRPL). "
                            "Answer the user request concisely, factually, and crisply in 2-3 focused paragraphs or bullet points without filler or verbosity. "
                            "Cite source tables, files, or standards whenever available. "
                            "Do not hallucinate operational figures; ground all specific plant values directly in the worker evidence."
                        ),
                    },
                    {
                        "role": "user",
                        "content":
                            f"Request: {request}\n"
                            f"Worker results: {evidence}",
                    },
                ],
                max_tokens=750,
                temperature=0.15,
            )

            cleaned = re.sub(
                r"<think>.*?(?:</think>|$)",
                "",
                resp,
                flags=re.DOTALL
            ).strip()

            final_text = cleaned or resp.strip()
            if not final_text:
                return self._build_fallback_response(request, results)
            return final_text

        except Exception as error:

            self.auditor.log_event(
                "RESPONSE_LLM_FAILURE",
                "localhost",
                (
                    f"Supervisor response LLM '{self.LLM_MODEL}' "
                    f"failed: {error}. "
                    "Using deterministic worker-result response."
                )
            )

            return self._build_fallback_response(
                request,
                results
            )

    # -----------------------------------------------------------------------
    # REPORT
    # -----------------------------------------------------------------------

    def write_report(
        self,
        request: str,
        plan: dict[str, Any],
        results: list[dict[str, Any]],
        answer: str,
    ) -> str:
        """Saves an audit report with sovereign air-gap telemetry."""

        now = datetime.now(timezone.utc)

        report_path = (
            self.settings.report_dir
            / (
                f"supervisor_report_"
                f"{now:%Y%m%d_%H%M%S}_"
                f"{uuid.uuid4().hex[:8]}.md"
            )
        )

        telemetry = (
            self.auditor.get_telemetry()
        )

        cert = (
            self.auditor.generate_audit_certificate()
        )

        raw_plan = json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
            default=str
        )

        raw_results = json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
            default=str
        )

        report_path.write_text(
            f"# MRPL Sovereign Supervisor Report\n\n"
            f"**Organization:** "
            f"Mangalore Refinery and Petrochemicals Limited (MRPL)\n"
            f"**Created (UTC):** "
            f"{now:%Y-%m-%dT%H:%M:%SZ}\n"
            f"**Air-Gap Status:** "
            f"{telemetry['sovereignty_status']} "
            f"(External WAN Bytes: "
            f"{telemetry['outbound_internet_bytes']})\n"
            f"**Supervisor LLM:** "
            f"`{self.LLM_MODEL}`\n"
            f"**Sovereign Audit Signature:** "
            f"`{cert['sha256_audit_signature']}`\n\n"
            f"## User Query\n\n"
            f"{request}\n\n"
            f"## Synthesized Response\n\n"
            f"{answer}\n\n"
            f"## Multi-Step Action Plan\n\n"
            f"```json\n"
            f"{raw_plan}\n"
            f"```\n\n"
            f"## Complete Evidence From Deterministic Workers\n\n"
            f"```json\n"
            f"{raw_results}\n"
            f"```\n",
            encoding="utf-8",
        )

        return str(
            report_path.resolve()
        )

    # -----------------------------------------------------------------------
    # PUBLIC API
    # -----------------------------------------------------------------------

    def handle(
        self,
        request: str,
        files: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        One-call public API:

        plan → execute → respond → save report

        Normal mode:
            LLM-powered planning + LLM response synthesis.

        Failure / Offline mode:
            Deterministic routing + deterministic response.
        """

        files = files or []
        llm_online = self._llm_available()

        # ---------------------------------------------------------------
        # PLAN
        # ---------------------------------------------------------------

        plan = self.plan(
            request,
            files
        )

        # ---------------------------------------------------------------
        # EXECUTE
        # ---------------------------------------------------------------

        results = self.execute(
            plan
        )

        # ---------------------------------------------------------------
        # RESPOND
        # ---------------------------------------------------------------

        if plan.get("fallback_mode") or not llm_online:
            answer = self._build_fallback_response(
                request,
                results
            )
        else:
            answer = self.respond(
                request,
                results
            )

        # ---------------------------------------------------------------
        # REPORT
        # ---------------------------------------------------------------

        report_path = self.write_report(
            request,
            plan,
            results,
            answer
        )

        telemetry = (
            self.auditor.get_telemetry()
        )

        is_llm_mode = llm_online and not plan.get("fallback_mode")

        return {
            "plan": plan,
            "results": results,
            "answer": answer,
            "report_path": report_path,
            "telemetry": telemetry,
            "routing": {
                "mode": "llm_orchestrated" if is_llm_mode else "deterministic_offline_fallback",
                "model_id": self.LLM_MODEL if is_llm_mode else "keyword_heuristic_planner",
                "reason": (
                    f"Ollama is online: LLM '{self.LLM_MODEL}' generated the plan and synthesized the grounded response."
                    if is_llm_mode
                    else "Deterministic fallback matched keywords to execute agents and returned direct outputs."
                )
            }
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Run the MRPL Sovereign Supervisor."
    )

    parser.add_argument(
        "request",
        help="Natural-language request for the supervisor"
    )

    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="A user-supplied local file (repeatable)"
    )

    args = parser.parse_args()

    print(
        json.dumps(
            SupervisorAgent().handle(
                args.request,
                args.file
            ),
            indent=2,
            default=str
        )
    )