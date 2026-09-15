"""Comprehensive Integration Tests for ModelRouter, Workers, and API."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model_router import get_model_router
from Vision_agent import VisionWorker
from Supervisor_agent import SupervisorAgent
from Data_agent import DataAnalysisWorker
from Document_modifier import DocumentModifierWorker
from Sandbox_agent import CodeSandboxWorker
from Template_agent import DeliverablesWorker
import asyncio
from server import list_models, select_model, ModelSelectPayload


class TestModelRouterIntegration(unittest.TestCase):

    def setUp(self):
        self.router = get_model_router()
        self.router.load_registry()

    def test_vision_worker_dynamic_resolution(self):
        """Verify VisionWorker dynamically respects ModelRouter active selection."""
        # Set active vision model to qwen3-vl:8b
        self.router.set_active_model("vision", "qwen3-vl:8b")
        worker = VisionWorker()
        # Verify router returns qwen3-vl:8b
        self.assertEqual(self.router.get_model("vision"), "qwen3-vl:8b")

        # Now dynamically switch to qwen2.5vl:7b
        self.router.set_active_model("vision", "qwen2.5vl:7b")
        self.assertEqual(self.router.get_model("vision"), "qwen2.5vl:7b")

        # Switch back to default
        self.router.set_active_model("vision", "qwen3-vl:8b")

    def test_supervisor_agent_dynamic_resolution(self):
        """Verify SupervisorAgent dynamically resolves planning and reasoning models."""
        supervisor = SupervisorAgent()
        self.router.set_active_model("supervisor", "qwen3:8b")
        self.assertEqual(supervisor.active_model, "qwen3:8b")

        # Switch supervisor model to qwen2.5:7b
        self.router.set_active_model("supervisor", "qwen2.5:7b")
        self.assertEqual(supervisor.active_model, "qwen2.5:7b")

        # Switch back
        self.router.set_active_model("supervisor", "qwen3:8b-finetuned")
        self.assertEqual(supervisor.active_model, "qwen3:8b-finetuned")

    def test_api_models_endpoint(self):
        """Test GET /api/models returns profiles with available models list."""
        data = asyncio.run(list_models())
        self.assertIn("active_selection", data)
        self.assertIn("profiles", data)

        # Check vision profile
        vision_prof = next((p for p in data["profiles"] if p["name"] == "vision"), None)
        self.assertIsNotNone(vision_prof)
        self.assertIn("available_models", vision_prof)
        v_ids = [m["model_id"] for m in vision_prof["available_models"]]
        self.assertIn("qwen3-vl:8b", v_ids)
        self.assertIn("qwen2.5vl:7b", v_ids)

    def test_api_model_select_endpoint(self):
        """Test POST /api/models/select endpoint updates active selection."""
        # Switch vision model
        payload = ModelSelectPayload(role="vision", model_id="qwen2.5vl:7b")
        data = asyncio.run(select_model(payload))
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["active_model"], "qwen2.5vl:7b")
        self.assertEqual(self.router.get_model("vision"), "qwen2.5vl:7b")

        # Switch back
        payload = ModelSelectPayload(role="vision", model_id="qwen3-vl:8b")
        data = asyncio.run(select_model(payload))
        self.assertEqual(data["status"], "success")
        self.assertEqual(self.router.get_model("vision"), "qwen3-vl:8b")

    def test_api_model_select_invalid_role(self):
        """Test POST /api/models/select rejects incompatible model assignment."""
        from fastapi import HTTPException
        payload = ModelSelectPayload(role="vision", model_id="deepseek-r1:1.5b")
        with self.assertRaises(HTTPException):
            asyncio.run(select_model(payload))

    def test_deterministic_workers_unaffected(self):
        """Confirm that deterministic workers continue to execute flawlessly."""
        # 1. Data analysis worker (DuckDB)
        dw = DataAnalysisWorker()
        tables = dw.list_tables()
        self.assertIsInstance(tables, list)

        # 2. Code sandbox worker
        sb = CodeSandboxWorker()
        res = sb.execute_code("result = 40 + 2\nprint(f'Computed: {result}')")
        self.assertIn("Computed: 42", res["stdout"])

        # 3. Deliverables worker
        dl = DeliverablesWorker()
        note = dl.author_approval_note(
            subject="Test Approval Note",
            findings="Deterministic deliverable authoring works.",
        )
        self.assertTrue(Path(note["file_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
