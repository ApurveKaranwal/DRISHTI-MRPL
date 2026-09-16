"""Unit test for ModelRouter and ModelRegistry in DRISHTI-MRPL."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model_router import ModelRouter, get_model_router


class TestModelRouter(unittest.TestCase):

    def setUp(self):
        # Use isolated router instance with default registry
        self.router = get_model_router()
        self.router.load_registry()

    def test_default_role_resolution(self):
        self.assertEqual(self.router.get_model("supervisor"), "qwen3:8b-finetuned")
        self.assertEqual(self.router.get_model("code"), "qwen2.5:7b")
        self.assertEqual(self.router.get_model("vision"), "qwen2.5vl:7b")
        self.assertEqual(self.router.get_model("reasoning"), "deepseek-r1:1.5b")

    def test_get_available_models_for_role(self):
        vision_models = self.router.get_available_models_for_role("vision")
        model_ids = [m["model_id"] for m in vision_models]
        self.assertIn("qwen3-vl:8b", model_ids)
        self.assertIn("qwen2.5vl:7b", model_ids)
        self.assertNotIn("deepseek-r1:1.5b", model_ids)

    def test_switch_active_model_valid(self):
        # Switch vision model to qwen3-vl:8b
        ok, msg = self.router.set_active_model("vision", "qwen3-vl:8b")
        self.assertTrue(ok, msg)
        self.assertEqual(self.router.get_model("vision"), "qwen3-vl:8b")

        # Switch back to qwen2.5vl:7b
        ok, msg = self.router.set_active_model("vision", "qwen2.5vl:7b")
        self.assertTrue(ok, msg)
        self.assertEqual(self.router.get_model("vision"), "qwen2.5vl:7b")

    def test_switch_active_model_invalid_role(self):
        # deepseek-r1:1.5b does not have vision role
        ok, msg = self.router.set_active_model("vision", "deepseek-r1:1.5b")
        self.assertFalse(ok)
        self.assertIn("only supports roles", msg)

    def test_switch_active_model_unregistered(self):
        ok, msg = self.router.set_active_model("vision", "nonexistent-model:99b")
        self.assertFalse(ok)
        self.assertIn("not in the registry", msg)

    def test_model_config(self):
        cfg = self.router.get_model_config("code")
        self.assertEqual(cfg["model_id"], "qwen2.5:7b")
        self.assertIn("temperature", cfg)
        self.assertIn("context_window", cfg)

    def test_register_new_model(self):
        test_id = "test-custom-llm:8b"
        ok, msg = self.router.register_model(
            model_id=test_id,
            roles=["general", "code"],
            capabilities=["text", "code"],
            description="A test code and general model",
            vram_estimate_gb=4.0,
        )
        self.assertTrue(ok)
        available = [m["model_id"] for m in self.router.get_available_models_for_role("code")]
        self.assertIn(test_id, available)

        # Cleanup test entry
        with self.router._file_lock:
            if test_id in self.router._registry_data.get("models", {}):
                del self.router._registry_data["models"][test_id]
                self.router.save_registry()


if __name__ == "__main__":
    unittest.main()
