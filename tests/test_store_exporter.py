import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from research_vault.sdk_client import Segment, VideoData
from research_vault import exporter, store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.tmp.name) / "vault.db")
        self.video = VideoData(
            "https://example.org/video/one", "The Searchable Talk", "en",
            (Segment("A search engine finds the data.", 2000, 3000),
             Segment("Use Python and SQLite for a knowledge vault.", 5000, 3500)),
            "A search engine finds the data.\nUse Python and SQLite for a knowledge vault.",
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_database_init_and_empty_search(self):
        self.assertEqual(store.stats(self.db)["videos"], 0)
        self.assertEqual(store.search(self.db, "hello"), [])

    def test_upsert_and_search(self):
        key = store.upsert(self.db, self.video)
        self.assertEqual(key, store.stable_id(self.video.url))
        self.assertEqual(store.stats(self.db)["segments"], 2)
        self.assertEqual(store.search(self.db, "Python")[0]["id"], key)
        self.assertEqual(store.search(self.db, "unmentioned"), [])
        # FTS5 punctuation should not create syntax errors.
        self.assertEqual(store.search(self.db, 'Python: "SQLite" [x]'), [])

    def test_upsert_replaces_segments_and_index(self):
        key = store.upsert(self.db, self.video)
        replacement = VideoData(self.video.url, "Updated", "en", (Segment("Replacement content"),), "Replacement content")
        store.upsert(self.db, replacement)
        self.assertEqual(store.stats(self.db)["videos"], 1)
        self.assertEqual(store.stats(self.db)["segments"], 1)
        self.assertEqual(store.search(self.db, "Replacement")[0]["id"], key)
        self.assertEqual(store.search(self.db, "SQLite"), [])

    def test_export_markdown_and_json(self):
        key = store.upsert(self.db, self.video)
        row = store.by_id(self.db, key)
        out = Path(self.tmp.name) / "out"
        md = exporter.export_video(self.db, row, out, "md")
        text = md.read_text(encoding="utf-8")
        self.assertIn("**[00:02]** A search", text)
        self.assertIn("https://example.org/video/one", text)
        js = exporter.export_video(self.db, row, out, "json")
        data = json.loads(js.read_text(encoding="utf-8"))
        self.assertEqual(data["segments"][0]["offset_ms"], 2000)
        self.assertEqual(data["lang"], "en")

    def test_time_formats(self):
        self.assertEqual(exporter.stamp(None), "--:--")
        self.assertEqual(exporter.stamp(135000), "02:15")
        self.assertEqual(exporter.stamp(3700000), "01:01:40")

    def test_unknown_video(self):
        self.assertIsNone(store.by_id(self.db, "notfound"))


if __name__ == "__main__":
    unittest.main()
