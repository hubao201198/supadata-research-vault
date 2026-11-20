"""SQLite persistence and full-text search for collected transcripts."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sdk_client import Segment, VideoData

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    lang TEXT NOT NULL,
    transcript TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'sdk',
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS segments (
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    offset_ms INTEGER,
    duration_ms INTEGER,
    content TEXT NOT NULL,
    PRIMARY KEY (video_id, position)
);
CREATE VIRTUAL TABLE IF NOT EXISTS video_fts USING fts5(
    video_id UNINDEXED, title, transcript, tokenize='unicode61 remove_diacritics 2'
);
"""


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db


def upsert(db: sqlite3.Connection, video: VideoData, *, source_kind: str = "sdk") -> str:
    video_id = stable_id(video.url)
    with db:
        db.execute(
            """INSERT INTO videos(id, url, title, lang, transcript, source_kind, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 url=excluded.url, title=excluded.title, lang=excluded.lang,
                 transcript=excluded.transcript, source_kind=excluded.source_kind,
                 imported_at=excluded.imported_at""",
            (video_id, video.url, video.title, video.lang, video.transcript,
             source_kind, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        db.execute("DELETE FROM segments WHERE video_id=?", (video_id,))
        db.executemany(
            "INSERT INTO segments(video_id,position,offset_ms,duration_ms,content) VALUES(?,?,?,?,?)",
            [(video_id, i, s.offset_ms, s.duration_ms, s.text)
             for i, s in enumerate(video.segments)],
        )
        db.execute("DELETE FROM video_fts WHERE video_id=?", (video_id,))
        db.execute(
            "INSERT INTO video_fts(video_id,title,transcript) VALUES(?,?,?)",
            (video_id, video.title, video.transcript),
        )
    return video_id


def by_id(db: sqlite3.Connection, identifier: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM videos WHERE id=? OR url=?", (identifier, identifier)
    ).fetchone()


def segments_for(db: sqlite3.Connection, video_id: str) -> list[Segment]:
    rows = db.execute(
        "SELECT * FROM segments WHERE video_id=? ORDER BY position", (video_id,)
    )
    return [Segment(r["content"], r["offset_ms"], r["duration_ms"]) for r in rows]


def list_videos(db: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return list(db.execute("SELECT * FROM videos ORDER BY imported_at DESC, id LIMIT ?", (limit,)))


def search(db: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    # FTS5 operators are powerful but confusing for a user search; quote terms.
    # This also prevents malformed FTS syntax from breaking ordinary queries.
    tokens = re.findall(r"[^\s\"*():]+", query, flags=re.UNICODE)
    if not tokens:
        return []
    safe_query = " AND ".join('"' + t.replace('"', '""') + '"' for t in tokens[:12])
    return list(db.execute(
        """SELECT v.id, v.title, v.url, v.lang, v.source_kind,
                  snippet(video_fts, 2, '[', ']', ' … ', 15) AS excerpt
           FROM video_fts JOIN videos v ON v.id = video_fts.video_id
           WHERE video_fts MATCH ? ORDER BY bm25(video_fts) LIMIT ?""",
        (safe_query, limit),
    ))


def stats(db: sqlite3.Connection) -> dict[str, Any]:
    v = db.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    s = db.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
    words = db.execute("SELECT SUM(LENGTH(transcript)) FROM videos").fetchone()[0] or 0
    return {"videos": v, "segments": s, "transcript_characters": words}
