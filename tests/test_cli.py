import io
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr, closing
from unittest.mock import patch
from types import SimpleNamespace
from research_vault.cli import main
from research_vault import store


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = str(Path(self.tmp.name) / "demo.db")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            ret = main(["--db", self.dbpath, *args])
        return ret, output.getvalue()

    def test_demo_and_search_and_export(self):
        rc, out = self.call("demo")
        self.assertEqual(rc, 0)
        self.assertIn("NO API call", out)
        self.assertEqual(self.call("search", "research")[0], 0)
        self.assertIn("synthetic", self.call("list")[1])
        self.assertIn("videos: 1", self.call("stats")[1])
        folder = str(Path(self.tmp.name) / "notes")
        self.assertEqual(self.call("export", "--dir", folder)[0], 0)
        self.assertEqual(len(list(Path(folder).glob("*.md"))), 1)

    def test_missing_key_is_handled(self):
        with patch.dict("os.environ", {}, clear=True), redirect_stderr(io.StringIO()) as errors:
            rc, _ = self.call("add", "https://youtu.be/demo")
        self.assertEqual(rc, 2)
        self.assertIn("SUPADATA_API_KEY", errors.getvalue())

    def test_actual_sdk_path_can_be_mocked(self):
        mocked = SimpleNamespace(content=[SimpleNamespace(text="Transcript from SDK", offset=0, duration=3000)], lang="en")
        class SDK:
            def __init__(self):
                self.calls = 0
            def transcript(self, **kwargs):
                self.calls += 1
                self.kwargs = kwargs
                return mocked
        fake = SDK()
        with patch.dict("os.environ", {"SUPADATA_API_KEY": "test-key"}), patch(
            "research_vault.sdk_client.create_sdk_client", return_value=fake
        ):
            rc, out = self.call("add", "https://youtu.be/demo", "--mode", "native", "--title", "Demo talk")
        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, 1)
        self.assertFalse(fake.kwargs["text"])
        with closing(store.connect(self.dbpath)) as db:
            self.assertEqual(store.stats(db)["videos"], 1)
            self.assertEqual(store.search(db, "SDK")[0]["title"], "Demo talk")

    def test_add_file_partial_errors_do_not_block_rest(self):
        urls = Path(self.tmp.name) / "urls.txt"
        urls.write_text("# comment\nhttps://youtu.be/ok\nnot-a-url\n", encoding="utf-8")
        fake = SimpleNamespace(transcript=lambda **kwargs: SimpleNamespace(content="hello world", lang="en"))
        with patch.dict("os.environ", {"SUPADATA_API_KEY": "test-key"}), patch(
            "research_vault.sdk_client.create_sdk_client", return_value=fake
        ), redirect_stderr(io.StringIO()):
            rc, _ = self.call("add-file", str(urls))
        self.assertEqual(rc, 1)
        with closing(store.connect(self.dbpath)) as db:
            self.assertEqual(store.stats(db)["videos"], 1)


if __name__ == "__main__":
    unittest.main()
