import unittest
from pathlib import Path

import yaml

from controllable_rag.config import Settings
from controllable_rag.index_manifest import inspect_index_manifest

ROOT = Path(__file__).resolve().parents[1]


class DeliveryConfigTests(unittest.TestCase):
    def test_dockerfile_has_runtime_safety_controls(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.11-slim-bookworm", dockerfile)
        self.assertIn("USER app", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertNotIn("rustup", dockerfile)

    def test_docker_context_excludes_secrets_and_local_artifacts(self):
        entries = {
            line.strip()
            for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        for expected in (".env", "venv", "evaluation/results", "vector_store_backups"):
            self.assertIn(expected, entries)

    def test_compose_uses_standard_dockerfile_and_qwen_configuration(self):
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        service = compose["services"]["web"]
        self.assertEqual(service["build"]["dockerfile"], "Dockerfile")
        self.assertIn("QWEN_API_KEY", service["environment"])
        self.assertNotIn("volumes", service)

    def test_ci_is_offline_and_docs_are_trackable(self):
        workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        workflow_config = yaml.safe_load(workflow)
        development = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        ruff_config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("on", workflow_config)
        self.assertIn("test", workflow_config["jobs"])
        self.assertIn("python -m ruff check", workflow)
        self.assertIn("python -m unittest discover -v", workflow)
        self.assertIn("audit_dataset.py", workflow)
        self.assertIn("-r requirements-runtime.txt", development)
        self.assertIn("ruff==0.16.7", development)
        self.assertIn('select = ["E4", "E7", "E9", "F", "I"]', ruff_config)
        ignored = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        }
        self.assertNotIn("docs/", ignored)

    def test_delivery_uses_validated_modern_langgraph_without_legacy_constraints(self):
        runtime = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("langgraph==1.2.11", runtime)
        self.assertIn("langgraph-checkpoint-sqlite==3.1.1", runtime)
        self.assertNotIn("-c requirements.txt", dockerfile)
        self.assertNotIn("-c requirements.txt", workflow)
        rebuild = (ROOT / "rebuild_vector_stores.py").read_text(encoding="utf-8")
        self.assertIn("write_index_manifest", rebuild)
        self.assertTrue((ROOT / "index_manifest.json").is_file())
        report = inspect_index_manifest(Settings(project_root=ROOT, api_key="ci-probe"))
        self.assertEqual(report["manifest"]["status"], "ready")
        self.assertEqual(report["embedding_contract"]["status"], "ready")
        self.assertTrue(all(
            item["status"] == "ready" for item in report["indexes"].values()
        ))


if __name__ == "__main__":
    unittest.main()
