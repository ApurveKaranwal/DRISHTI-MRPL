"""MRPL Sovereign AI Workbench — Supervisor Agent.

Orchestrates six deterministic local workers:
1. document_retrieval: indexes & searches document evidence (MRPL SOPs, API standards).
2. data_analysis: loads CSV/TSV/XLS/XLSX into DuckDB and runs read-only SQL.
3. vision: runs Tesseract OCR and local VLM on images and scanned PDF pages.
4. document_modifier: creates new edited versions of existing DOCX/XLSX/PPTX/PDF/CSV.
5. code_sandbox: executes Python code in an isolated local sandbox with stdout/plot capture.
6. template_author: authors formal MRPL Approval Notes (.docx), presentations (.pptx), and calculation sheets (.xlsx).

Features:
- Dynamic Model Routing across open-weight models (Qwen 2.5 Coder, DeepSeek-R1-Distill, Qwen2-VL, Qwen 2.5).
- Air-Gap Sovereign Network Telemetry proving 0 external WAN packets.
- Self-healing plan validation with SQL AST & column normalization.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
from Model_router import ModelRouter, RoutingDecision

_SUFFIX_TO_MODIFIER_FORMAT: dict[str, str] = {
    **{s: "docx" for s in DOCX_SUFFIXES},
    **{s: "xlsx" for s in XLSX_SUFFIXES},
    **{s: "pptx" for s in PPTX_SUFFIXES},
    **{s: "pdf" for s in PDF_SUFFIXES},
    **{s: "csv" for s in CSV_SUFFIXES},
}


AGENT_CONTEXT = """You supervise six deterministic local workers for Mangalore Refinery and Petrochemicals Limited (MRPL):
1. document_retrieval: indexes/searches internal standards, SOPs, and manuals with hybrid retrieval.
   Returns source chunks, not an answer.
2. data_analysis: loads CSV/TSV/XLS/XLSX into DuckDB and runs read-only SQL.
   Use it for exact sums, averages, filters, group-bys, schemas, and tables.
3. vision: runs Tesseract OCR plus a local VLM on images or scanned PDF pages (P&IDs, inspection sheets).
   OCR is exact extraction; VLM describes visual features/trends.
4. document_modifier: creates a new edited DOCX/XLSX/PPTX/PDF/CSV. Only accepts typed operations.
5. code_sandbox: executes Python scripts in an isolated local sandbox for hydraulic/engineering calculations,
   algorithms, and matplotlib plot generation.
6. template_author: generates formal PSU deliverables from scratch:
   - author_approval_note: generates a formal MRPL Internal Approval Note (.docx) in standard PSU memorandum format.
   - author_presentation: generates an executive briefing slide deck (.pptx).
   - author_calculation_sheet: generates an engineering calculation workbook (.xlsx).

Do not invent worker outputs. Select the smallest useful plan. Use a worker only when needed.
"""


@dataclass(frozen=True)
class SupervisorSettings:
    scratch_dir: Path = Path(os.getenv("SUPERVISOR_DATA_DIR", "./data/supervisor"))
    report_dir: Path = Path(os.getenv("SUPERVISOR_REPORT_DIR", "./outputs/reports"))


class SupervisorAgent:
    """Routes user requests to local workers and synthesizes grounded results."""

    def __init__(
        self,
        settings: SupervisorSettings | None = None,
        router: ModelRouter | None = None,
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
        self.settings.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.settings.report_dir.mkdir(parents=True, exist_ok=True)
        
        self.router = router or ModelRouter()
        self.document_worker = document_worker
        self.data_worker = data_worker
        self.vision_worker = vision_worker
        self.modifier_worker = modifier_worker
        self.sandbox_worker = sandbox_worker
        self.template_worker = template_worker
        self.auditor = auditor or SovereignNetworkAuditor(self.settings.report_dir)

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

    def _known_tables_context(self) -> str:
        tables = self._data().list_tables()
        if not tables:
            return "No tables are currently loaded in data_analysis."
        lines = []
        for t in tables:
            tname = t["table_name"]
            try:
                col_info = self._data().conn.execute(f'PRAGMA table_info("{tname}")').fetchall()
                col_names = [r[1] for r in col_info]
                cols_str = ", ".join(col_names)
            except Exception:
                cols_str = f"{t['column_count']} cols"
            lines.append(f'- "{tname}" ({t["row_count"]} rows): [{cols_str}]')
        return "Tables and exact column names loaded in data_analysis (use these EXACT table and column names in SQL):\n" + "\n".join(lines)

    def _modifier_schema_context(self) -> str:
        lines = []
        for fmt in sorted(OPS_BY_FORMAT):
            for op_type in sorted(OPS_BY_FORMAT[fmt]):
                required = sorted(REQUIRED_KEYS_BY_OP[op_type])
                lines.append(f'- .{fmt} file, "type": "{op_type}" — required fields: {required}')
        return (
            "document_modifier operation types (use ONLY these \"type\" values, with "
            "EXACTLY these required fields present on every operation object):\n" + "\n".join(lines)
        )

    def plan(
        self,
        request: str,
        files: list[str] | None = None,
        routing_override: RoutingDecision | None = None,
        *,
        max_attempts: int = 3
    ) -> tuple[dict[str, Any], RoutingDecision]:
        """Auto-routes to the optimal model and generates a validated JSON execution plan."""
        routing = routing_override or self.router.route(request, files)
        self.auditor.log_event("PLANNING_DISPATCH", "localhost", f"Routed to profile '{routing.profile}' ({routing.model_id})")

        base_prompt = f"""{AGENT_CONTEXT}
{self._known_tables_context()}

{self._modifier_schema_context()}

CRITICAL PLANNING RULES:
1. If the user asks an operational question or root-cause diagnostic (e.g., about temperatures, pressures, alerts), use 'document_retrieval' with action 'search' to find relevant procedures/standards, or leave 'actions': [] to answer directly.
2. ONLY invoke 'data_analysis' with 'query' if you provide a valid read-only SQL query in 'sql' (e.g. SELECT ...) over known tables. NEVER put natural language inside 'sql'.
3. ONLY invoke 'vision' if an image or scan file is explicitly supplied.

Return JSON only, with this exact shape:
{{"actions": [{{"worker": "document_retrieval|data_analysis|vision|document_modifier|code_sandbox|template_author",
"action": "search|ingest|query|schema|describe|process_image|process_scanned_pdf|modify|execute_code|author_approval_note|author_presentation|author_calculation_sheet",
"file": "optional path", "query": "optional text", "sql": "optional read-only SQL",
"operations": ["optional modifier ops"], "code": "optional python code string",
"note_data": {{"ref_no": "str", "department": "str", "subject": "str", "approving_authority": "str", "background": "str", "findings": "str", "safety_compliance": "str", "financial_impact": "str", "recommendations": "str"}}
}}], "reply_goal": "short description"}}

User request: {request}
Files explicitly supplied: {files or []}
"""
        messages = [
            {"role": "system", "content": "You are a careful task planner for MRPL. " + AGENT_CONTEXT},
            {"role": "user", "content": base_prompt},
        ]
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            raw = self.router.chat(messages, profile=routing.profile, json_mode=True)
            try:
                # Strip reasoning tags (e.g. DeepSeek R1 <think>)
                cleaned_raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                json_match = re.search(r"(\{.*\})", cleaned_raw, flags=re.DOTALL)
                raw_json = json_match.group(1) if json_match else cleaned_raw
                plan = json.loads(raw_json)
                self._validate_plan(plan)
                self._validate_plan_files(plan, files or [])
                self._validate_modify_operations(plan)
                return plan, routing
            except (json.JSONDecodeError, ValueError) as error:
                last_error = error
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": f"JSON was invalid: {error}. Return corrected JSON only.",
                })

        # Resilient operational fallback plan instead of fatal exception
        default_plan = self._generate_fallback_plan(request, files or [], routing)
        return default_plan, routing

    def _generate_fallback_plan(
        self,
        request: str,
        files: list[str],
        routing: RoutingDecision,
    ) -> dict[str, Any]:
        """Generates a guaranteed-valid execution plan if local LLM planning runs into edge cases."""
        actions: list[dict[str, Any]] = []
        img_files = [f for f in files if Path(f).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}]
        if img_files:
            actions.append({"worker": "vision", "action": "process_image", "file": img_files[0]})

        csv_files = [f for f in files if Path(f).suffix.lower() in {".csv", ".tsv", ".xlsx", ".xls"}]
        if csv_files:
            actions.append({"worker": "data_analysis", "action": "describe", "file": csv_files[0]})

        if not actions:
            actions.append({
                "worker": "document_retrieval",
                "action": "search",
                "query": request[:120],
            })

        return {
            "actions": actions,
            "reply_goal": f"Execute operational analysis for: {request[:80]}",
        }

    @staticmethod
    def _validate_plan_files(plan: dict[str, Any], files: list[str]) -> None:
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
            worker, name = action.get("worker"), action.get("action")
            file_path = action.get("file")
            if file_path:
                # Check root or data/ directory
                if file_path in allowed or Path(file_path).is_file() or file_path.startswith("data/"):
                    continue
                if (Path("data") / file_path).is_file():
                    action["file"] = str(Path("data") / file_path)
                    continue
            if (worker, name) in file_requiring_actions and file_path and file_path not in allowed:
                # Model hallucinated an unsupplied file: redirect to general document search
                if worker == "data_analysis":
                    action["worker"] = "document_retrieval"
                    action["action"] = "search"
                    action["query"] = action.get("query") or f"MRPL {name} data"
                    action.pop("file", None)
                    action.pop("sql", None)
                else:
                    action["file"] = None

    @staticmethod
    def _validate_modify_operations(plan: dict[str, Any]) -> None:
        for index, action in enumerate(plan.get("actions", [])):
            if action.get("worker") != "document_modifier" or action.get("action") != "modify":
                continue
            file_path = action.get("file")
            operations = action.get("operations")
            if not isinstance(operations, list) or not operations:
                raise ValueError(f"actions[{index}]: document_modifier.modify requires non-empty 'operations'.")
            suffix = Path(str(file_path)).suffix.lower()
            fmt = _SUFFIX_TO_MODIFIER_FORMAT.get(suffix)
            if fmt is None:
                raise ValueError(f"actions[{index}]: unsupported format '{suffix}'.")
            allowed_ops = OPS_BY_FORMAT[fmt]
            for op_index, op in enumerate(operations):
                if not isinstance(op, dict):
                    raise ValueError(f"actions[{index}].operations[{op_index}] must be a dict.")
                op_type = op.get("type")
                if op_type not in REQUIRED_KEYS_BY_OP or op_type not in allowed_ops:
                    raise ValueError(f"actions[{index}].operations[{op_index}]: invalid op '{op_type}'.")
                missing = REQUIRED_KEYS_BY_OP[op_type] - op.keys()
                if missing:
                    raise ValueError(f"actions[{index}].operations[{op_index}]: missing fields {sorted(missing)}")

    @staticmethod
    def _validate_plan(plan: Any) -> None:
        if not isinstance(plan, dict) or not isinstance(plan.get("actions"), list):
            raise ValueError("Plan must be an object containing an actions list.")
        allowed: dict[str, set[str]] = {
            "document_retrieval": {"search", "ingest"},
            "data_analysis": {"ingest", "query", "schema", "describe"},
            "vision": {"process_image", "process_scanned_pdf"},
            "document_modifier": {"modify"},
            "code_sandbox": {"execute_code"},
            "template_author": {"author_approval_note", "author_presentation", "author_calculation_sheet"},
        }
        valid_actions = []
        for index, action in enumerate(plan["actions"]):
            if not isinstance(action, dict):
                continue
            worker, name = action.get("worker"), action.get("action")
            if worker not in allowed or name not in allowed[worker]:
                continue
            if name == "query":
                sql = str(action.get("sql", "")).strip()
                if not sql.upper().startswith(("SELECT", "WITH")) or ";" in sql.rstrip(";"):
                    action["worker"] = "document_retrieval"
                    action["action"] = "search"
                    action["query"] = action.get("query") or sql or "MRPL process operations"
                    action.pop("sql", None)
            valid_actions.append(action)
        plan["actions"] = valid_actions

    def _resolve_table_name(self, data: DataAnalysisWorker, file_path: str) -> str:
        try:
            ingest_result = data.ingest(file_path)
            return ingest_result["tables"][0]["table_name"]
        except DuplicateFileError:
            source_name = Path(file_path).name
            for table in data.list_tables():
                if table["source_name"] == source_name:
                    return table["table_name"]
            raise

    def _rewrite_sql_table_reference(self, sql: str, file_path: str, table_name: str) -> str:
        stem = Path(file_path).stem
        pattern = re.compile(re.escape(stem) + r"(\.\w+)?")
        return pattern.sub(table_name, sql)

    def _rewrite_unknown_table_references(self, sql: str, data: DataAnalysisWorker) -> str:
        known = data.list_tables()
        if not known:
            return sql
        known_names = {t["table_name"] for t in known}
        referenced = set(re.findall(r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', sql, flags=re.IGNORECASE))
        for guess in referenced - known_names:
            candidates = {
                t["table_name"] for t in known
                if t["table_name"].startswith(guess) or Path(t["source_name"]).stem == guess
            }
            if len(candidates) == 1:
                real_name = next(iter(candidates))
                sql = re.sub(rf'\b{re.escape(guess)}\b', real_name, sql)
        return sql

    _SQL_RESERVED = {
        "select", "from", "where", "group", "by", "order", "having", "limit", "offset",
        "as", "and", "or", "not", "sum", "avg", "count", "min", "max", "distinct",
        "case", "when", "then", "else", "end", "on", "join", "left", "right", "inner",
        "outer", "full", "asc", "desc", "null", "is", "in", "like", "between", "with",
        "union", "all", "extract", "date", "month", "year", "day", "cast", "round",
        "over", "partition", "coalesce", "nullif", "true", "false",
    }

    def _rewrite_unknown_columns(self, sql: str, table_name: str, data: DataAnalysisWorker) -> str:
        try:
            real_columns = {c["name"] for c in data.schema(table_name)["columns"]}
        except ValueError:
            return sql
        tokens = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', sql))
        guesses = {
            token for token in tokens
            if token not in real_columns
            and token.lower() not in self._SQL_RESERVED
            and token != table_name
        }
        for guess in guesses:
            candidates = {c for c in real_columns if c.startswith(guess) or guess in c}
            if len(candidates) == 1:
                real_name = next(iter(candidates))
                sql = re.sub(rf'\b{re.escape(guess)}\b', real_name, sql)
        return sql

    def execute(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        """Executes a validated plan across the local workers with full telemetry logging."""
        self._validate_plan(plan)
        results: list[dict[str, Any]] = []
        for action in plan["actions"]:
            worker, name = action["worker"], action["action"]
            file_path = action.get("file")

            self.auditor.log_event("WORKER_EXECUTE", "localhost", f"Invoking {worker}.{name}")

            try:
                if worker == "document_retrieval":
                    doc = self._document()
                    result = doc.search(action.get("query", "")) if name == "search" else doc.ingest(file_path)

                elif worker == "data_analysis":
                    data = self._data()
                    if name == "query" and file_path:
                        table_name = self._resolve_table_name(data, file_path)
                        sql = self._rewrite_sql_table_reference(action["sql"], file_path, table_name)
                        sql = self._rewrite_unknown_columns(sql, table_name, data)
                        result = data.query(sql)
                    elif name == "query":
                        sql = self._rewrite_unknown_table_references(action["sql"], data)
                        referenced_tables = set(re.findall(
                            r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', sql, flags=re.IGNORECASE
                        ))
                        known_table_names = {t["table_name"] for t in data.list_tables()}
                        for referenced_table in referenced_tables & known_table_names:
                            sql = self._rewrite_unknown_columns(sql, referenced_table, data)
                        result = data.query(sql)
                    else:
                        result = {
                            "ingest": lambda: data.ingest(file_path),
                            "schema": lambda: data.schema(action["table_name"]),
                            "describe": lambda: data.describe(action["table_name"]),
                        }[name]()

                elif worker == "vision":
                    vision = self._vision()
                    result = vision.process_image(file_path) if name == "process_image" else vision.process_scanned_pdf(file_path)

                elif worker == "document_modifier":
                    result = self._modifier().modify(file_path, action["operations"])

                elif worker == "code_sandbox":
                    code_str = action.get("code", "")
                    result = self._sandbox().execute_code(code_str)

                elif worker == "template_author":
                    templ = self._template()
                    if name == "author_approval_note":
                        note_data = action.get("note_data", {})
                        result = templ.author_approval_note(**note_data)
                    elif name == "author_presentation":
                        result = templ.author_presentation(
                            action.get("title", "MRPL Briefing"),
                            action.get("subtitle", "Technical Services"),
                            action.get("slides_data", []),
                        )
                    else:
                        result = templ.author_calculation_sheet(
                            action.get("sheet_title", "Engineering Calculation"),
                            action.get("parameters", []),
                            action.get("results", []),
                        )
                else:
                    result = {"status": "unsupported"}

                results.append({"worker": worker, "action": name, "result": result})
            except Exception as err:
                results.append({"worker": worker, "action": name, "result": {"success": False, "error": str(err)}})

        return results

    def respond(self, request: str, results: list[dict[str, Any]], routing: RoutingDecision) -> str:
        """Synthesizes grounded worker results into a concise, professional answer."""
        evidence = json.dumps(results, default=str, ensure_ascii=False)
        return self.router.chat(
            [
                {"role": "system", "content": AGENT_CONTEXT + "\nAnswer using only the supplied worker results. Cite source_name when available."},
                {"role": "user", "content": f"Request: {request}\nWorker results: {evidence}"},
            ],
            profile=routing.profile,
        )

    def write_report(
        self,
        request: str,
        plan: dict[str, Any],
        results: list[dict[str, Any]],
        answer: str,
        routing: RoutingDecision
    ) -> str:
        """Saves an audit report with sovereign air-gap telemetry and certificate."""
        now = datetime.now(timezone.utc)
        report_path = self.settings.report_dir / (
            f"supervisor_report_{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.md"
        )
        telemetry = self.auditor.get_telemetry()
        cert = self.auditor.generate_audit_certificate()

        raw_plan = json.dumps(plan, indent=2, ensure_ascii=False, default=str)
        raw_results = json.dumps(results, indent=2, ensure_ascii=False, default=str)

        report_path.write_text(
            f"# MRPL Sovereign Supervisor Report\n\n"
            f"**Organization:** Mangalore Refinery and Petrochemicals Limited (MRPL)\n"
            f"**Created (UTC):** {now:%Y-%m-%dT%H:%M:%SZ}\n"
            f"**Air-Gap Status:** {telemetry['sovereignty_status']} (External WAN Bytes: {telemetry['outbound_internet_bytes']})\n"
            f"**Model Profile Selected:** `{routing.profile}` ({routing.model_id})\n"
            f"**Auto-Selection Rationale:** {routing.reason}\n"
            f"**Sovereign Audit Signature:** `{cert['sha256_audit_signature']}`\n\n"
            f"## User Query\n\n{request}\n\n"
            f"## Synthesized Response\n\n{answer}\n\n"
            f"## Multi-Step Action Plan\n\n````json\n{raw_plan}\n````\n\n"
            f"## Complete Evidence From Deterministic Workers\n\n````json\n{raw_results}\n````\n",
            encoding="utf-8",
        )
        return str(report_path.resolve())

    def handle(
        self,
        request: str,
        files: list[str] | None = None,
        routing_override: RoutingDecision | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """One-call public API: plan, execute, respond, and save full sovereign report."""
        plan, routing = self.plan(request, files, routing_override=routing_override)
        results = self.execute(plan)
        answer = self.respond(request, results, routing)
        report_path = self.write_report(request, plan, results, answer, routing)
        telemetry = self.auditor.get_telemetry()
        return {
            "routing": {
                "profile": routing.profile,
                "model_id": routing.model_id,
                "reason": routing.reason,
                "vram_estimate_gb": routing.vram_estimate_gb,
            },
            "plan": plan,
            "results": results,
            "answer": answer,
            "report_path": report_path,
            "telemetry": telemetry,
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the MRPL Sovereign Supervisor.")
    parser.add_argument("request", help="Natural-language request for the supervisor")
    parser.add_argument("--file", action="append", default=[], help="A user-supplied local file (repeatable)")
    args = parser.parse_args()
    print(json.dumps(SupervisorAgent().handle(args.request, args.file), indent=2, default=str))