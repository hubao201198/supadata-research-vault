"""Reject README-only submissions: all referenced implementation files must exist."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RepositoryCompletenessTests(unittest.TestCase):
    def test_files_exist_and_are_substantive(self):
        expected = [
            "README.md", "requirements.txt", "pyproject.toml", "LICENSE",
            "research_vault/__init__.py", "research_vault/__main__.py",
            "research_vault/sdk_client.py", "research_vault/store.py",
            "research_vault/exporter.py", "research_vault/cli.py",
            "tests/test_cli.py", "tests/test_sdk_client.py",
            "tests/test_store_exporter.py", "examples/demo-note.md",
            ".gitignore", ".github/workflows/tests.yml",
        ]
        for filename in expected:
            with self.subTest(filename=filename):
                file = ROOT / filename
                self.assertTrue(file.is_file(), filename)
                self.assertGreater(file.stat().st_size, 5)

    def test_readme_discloses_promotion_and_uses_official_sdk(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        implementation = (ROOT / "research_vault/sdk_client.py").read_text(encoding="utf-8")
        self.assertIn("https://supadata.ai/r/9YW9BZ05", readme)
        self.assertIn("Disclosure", readme)
        self.assertIn("from supadata import Supadata", implementation)
        self.assertIn("client.transcript.get_job_status(job_id)", implementation)


if __name__ == "__main__":
    unittest.main()
