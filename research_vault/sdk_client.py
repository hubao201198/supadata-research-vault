"""Supadata Python SDK adapter. No manual HTTP calls or unofficial wrappers.

Pinned SDK: supadata-ai/py commit 35b369f... (supports transcript.get_job_status).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse


class IngestionError(RuntimeError):
    """The SDK could not produce a usable transcript."""


@dataclass(frozen=True)
class Segment:
    text: str
    offset_ms: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class VideoData:
    url: str
    title: str
    lang: str
    segments: tuple[Segment, ...]
    transcript: str


def create_sdk_client(api_key: str) -> Any:
    """Import lazily so demo/search/tests need no installed SDK or API key."""
    if not api_key:
        raise IngestionError("SUPADATA_API_KEY is required to import real videos")
    try:
        from supadata import Supadata
    except ImportError as exc:
        raise IngestionError(
            'Install the official SDK first: python -m pip install -r requirements.txt'
        ) from exc
    return Supadata(api_key=api_key)


def resolve_transcript(
    client: Any,
    url: str,
    *,
    mode: str = "native",
    lang: str | None = None,
    interval: float = 1.0,
    max_wait: float = 300.0,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Any:
    """Call the official SDK and handle both immediate and 202 async results."""
    if mode not in {"native", "auto", "generate"}:
        raise ValueError("mode must be native, auto, or generate")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("A public https:// or http:// video URL is required")
    if interval <= 0 or max_wait <= 0:
        raise ValueError("poll interval and max wait must be positive")

    kwargs: dict[str, Any] = {"url": url, "text": False, "mode": mode}
    if lang:
        kwargs["lang"] = lang
    result = client.transcript(**kwargs)
    if hasattr(result, "content"):
        return result

    job_id = getattr(result, "job_id", None)
    if not job_id:
        raise IngestionError("SDK returned neither transcript content nor an async job ID")

    deadline = monotonic() + max_wait
    while monotonic() < deadline:
        sleep(min(interval, max(0.0, deadline - monotonic())))
        job = client.transcript.get_job_status(job_id)
        if job.status == "completed":
            if job.result is None:
                raise IngestionError("Completed job had no result")
            return job.result
        if job.status == "failed":
            raise IngestionError(f"Supadata transcript job failed: {job.error}")
        if job.status not in ("queued", "active"):
            raise IngestionError(f"Unexpected Supadata job state: {job.status!r}")
    raise IngestionError(f"Supadata job {job_id} timed out after {max_wait:g} seconds")


def normalize_transcript(url: str, result: Any, title: str | None = None) -> VideoData:
    """Normalize the official SDK Transcript object for local storage.

    text=False normally returns TranscriptChunk objects with millisecond offsets.
    This also tolerates a plain string so older/alternate SDK responses are readable.
    """
    content = getattr(result, "content", None)
    language = getattr(result, "lang", "") or "unknown"
    if isinstance(content, str):
        segments = [Segment(content)] if content.strip() else []
    elif isinstance(content, list):
        segments = []
        for chunk in content:
            text = getattr(chunk, "text", None)
            if isinstance(chunk, dict):
                text = chunk.get("text", "")
                offset = chunk.get("offset")
                duration = chunk.get("duration")
            else:
                offset = getattr(chunk, "offset", None)
                duration = getattr(chunk, "duration", None)
            if text and str(text).strip():
                segments.append(Segment(str(text).strip(), offset, duration))
    else:
        raise IngestionError("Unsupported content from Supadata SDK")
    if not segments:
        raise IngestionError("Supadata returned an empty transcript (no detected speech)")

    display_name = title.strip() if title and title.strip() else default_title(url)
    return VideoData(
        url=url,
        title=display_name,
        lang=language,
        segments=tuple(segments),
        transcript="\n".join(segment.text for segment in segments),
    )


def default_title(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug or slug == "watch":
        from urllib.parse import parse_qs
        slug = parse_qs(parsed.query).get("v", ["video"])[0]
    return f"{parsed.hostname} · {slug or 'video'}"


def fetch_video(
    client: Any,
    url: str,
    *,
    mode: str = "native",
    lang: str | None = None,
    title: str | None = None,
    metadata: bool = False,
    interval: float = 1.0,
    max_wait: float = 300.0,
) -> VideoData:
    result = resolve_transcript(
        client, url, mode=mode, lang=lang, interval=interval, max_wait=max_wait
    )
    if metadata and not title:
        try:
            details = client.metadata(url=url)
            title = getattr(details, "title", None)
        except Exception as exc:
            # A successful transcript is still useful when optional metadata fails.
            print(f"Warning: optional SDK metadata lookup failed: {exc}", file=__import__("sys").stderr)
    return normalize_transcript(url, result, title=title)
