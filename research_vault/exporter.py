"""Markdown/JSON export, preserving source URLs and timestamp provenance."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from .store import segments_for


def stamp(ms: int | None) -> str:
    if ms is None:
        return "--:--"
    seconds = max(0, int(ms)) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}" if hours else f"{minutes:02d}:{sec:02d}"


def note_text(db: sqlite3.Connection, row: sqlite3.Row) -> str:
    # Escape the title so it cannot accidentally become a Markdown heading block.
    title = str(row["title"]).replace("\n", " ").replace("\r", " ")
    parts = [
        f"# {title}", "",
        f"- Source: {row['url']}",
        f"- Language: {row['lang']}",
        f"- Imported: {row['imported_at']}",
        f"- Source kind: {row['source_kind']}", "", "## Transcript", "",
    ]
    for segment in segments_for(db, row["id"]):
        parts.append(f"**[{stamp(segment.offset_ms)}]** {segment.text}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def file_stem(row: sqlite3.Row) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", row["title"]).strip("-")[:48]
    return f"{name or 'video'}-{row['id']}"


def export_video(db: sqlite3.Connection, row: sqlite3.Row, directory: Path, fmt: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{file_stem(row)}.{fmt}"
    if fmt == "md":
        output.write_text(note_text(db, row), encoding="utf-8")
    elif fmt == "json":
        output.write_text(
            json.dumps(
                {"url": row["url"], "title": row["title"], "lang": row["lang"],
                 "imported_at": row["imported_at"], "source_kind": row["source_kind"],
                 "segments": [vars(s) for s in segments_for(db, row["id"])]},
                indent=2, ensure_ascii=False,
            ) + "\n", encoding="utf-8",
        )
    else:
        raise ValueError("format must be md or json")
    return output
