import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from research_vault.sdk_client import (
    IngestionError,
    normalize_transcript,
    resolve_transcript,
)


class OfficialSDKTests(unittest.TestCase):
    def test_sync_sdk_transcript_parameters(self):
        transcript = Mock(return_value=SimpleNamespace(content="Hello", lang="en"))
        client = SimpleNamespace(transcript=transcript)
        data = resolve_transcript(client, "https://youtu.be/abc", mode="native", lang="en")
        self.assertEqual(data.content, "Hello")
        transcript.assert_called_once_with(url="https://youtu.be/abc", text=False, mode="native", lang="en")

    def test_async_sdk_poll(self):
        class FakeTranscript:
            def __init__(self):
                self.polls = 0
                self.params = None
            def __call__(self, **kwargs):
                self.params = kwargs
                return SimpleNamespace(job_id="job-001")
            def get_job_status(self, job_id):
                self.assert_job_id = job_id
                self.polls += 1
                if self.polls == 1:
                    return SimpleNamespace(status="queued")
                if self.polls == 2:
                    return SimpleNamespace(status="active")
                return SimpleNamespace(status="completed", result=SimpleNamespace(
                    content=[SimpleNamespace(text="Hello", offset=0, duration=3000)], lang="en"))
        api = FakeTranscript()
        counter = iter(range(100))
        result = resolve_transcript(
            SimpleNamespace(transcript=api), "https://youtu.be/abc", interval=1,
            max_wait=100, sleep=lambda _: None, monotonic=lambda: next(counter),
        )
        self.assertEqual(api.polls, 3)
        self.assertEqual(api.assert_job_id, "job-001")
        self.assertEqual(result.content[0].text, "Hello")

    def test_async_failure(self):
        class Failure:
            def __call__(self, **kwargs):
                return SimpleNamespace(job_id="j")
            def get_job_status(self, job_id):
                return SimpleNamespace(status="failed", error={"title": "not available"})
        with self.assertRaisesRegex(IngestionError, "not available"):
            resolve_transcript(SimpleNamespace(transcript=Failure()), "https://youtu.be/x",
                               sleep=lambda _: None)

    def test_completed_without_result(self):
        class Bad:
            def __call__(self, **kwargs):
                return SimpleNamespace(job_id="j")
            def get_job_status(self, job_id):
                return SimpleNamespace(status="completed", result=None)
        with self.assertRaisesRegex(IngestionError, "no result"):
            resolve_transcript(SimpleNamespace(transcript=Bad()), "https://youtu.be/x",
                               sleep=lambda _: None)

    def test_bad_url_and_mode(self):
        client = SimpleNamespace(transcript=Mock())
        with self.assertRaises(ValueError):
            resolve_transcript(client, "not a url")
        with self.assertRaises(ValueError):
            resolve_transcript(client, "https://youtu.be/abc", mode="unapproved")

    def test_millisecond_chunks(self):
        value = normalize_transcript(
            "https://youtu.be/abc", SimpleNamespace(
                content=[SimpleNamespace(text=" first ", offset=0, duration=1400),
                         SimpleNamespace(text="second", offset=1400, duration=1800)], lang="en"),
            title="Example"
        )
        self.assertEqual(value.title, "Example")
        self.assertEqual(value.transcript, "first\nsecond")
        self.assertEqual(value.segments[1].offset_ms, 1400)

    def test_missing_transcript_rejected(self):
        with self.assertRaisesRegex(IngestionError, "empty"):
            normalize_transcript("https://youtu.be/abc", SimpleNamespace(content=[], lang="en"))

    def test_string_response(self):
        val = normalize_transcript("https://youtu.be/abc", SimpleNamespace(content="Plain text", lang="en"))
        self.assertEqual(val.segments[0].text, "Plain text")
        self.assertIsNone(val.segments[0].offset_ms)


if __name__ == "__main__":
    unittest.main()
