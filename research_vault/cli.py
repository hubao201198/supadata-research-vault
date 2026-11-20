"""Command-line app: create, ingest, search, inspect and export a video vault."""

from __future__ import annotations

import argparse
from contextlib import closing
import os
import sys
from pathlib import Path

from . import exporter, sdk_client, store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-vault",
        description="A searchable SQLite transcript vault powered by the Supadata Python SDK",
    )
    parser.add_argument("--db", type=Path, default=Path("vault.db"), help="SQLite database (default: vault.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create an empty searchable vault")
    sub.add_parser("demo", help="Seed an explicitly synthetic example; no SDK/API key needed")
    add = sub.add_parser("add", help="Fetch a public video via the official Supadata SDK")
    add.add_argument("url", help="Public YouTube/TikTok/Instagram/X/Facebook video URL")
    add_file = sub.add_parser("add-file", help="Import line-separated URLs from a UTF-8 file")
    add_file.add_argument("path", type=Path)
    for command in (add, add_file):
        command.add_argument("--mode", default="native", choices=("native", "auto", "generate"))
        command.add_argument("--lang", help="Preferred caption language, e.g., en or zh")
        command.add_argument("--metadata", action="store_true", help="Call SDK metadata endpoint for title (extra request)")
        command.add_argument("--interval", default=1.0, type=float, help="Async polling interval in seconds")
        command.add_argument("--max-wait", default=300.0, type=float, help="Max wait for async result in seconds")
    add.add_argument("--title", help="Optional display title; skips metadata lookup")
    search = sub.add_parser("search", help="Full-text search across all stored video transcripts")
    search.add_argument("query")
    search.add_argument("--limit", default=10, type=int)
    show = sub.add_parser("show", help="View metadata and up to 1600 characters of transcript")
    show.add_argument("id", help="Video ID or original URL")
    sub.add_parser("list", help="List all stored video titles and IDs")
    sub.add_parser("stats", help="Show vault statistics")
    export = sub.add_parser("export", help="Write Markdown or JSON notes from the database")
    export.add_argument("--id", help="Export one video (default: all)")
    export.add_argument("--format", default="md", choices=("md", "json"))
    export.add_argument("--dir", type=Path, default=Path("notes"), help="Output folder")
    return parser


def fake_example() -> sdk_client.VideoData:
    return sdk_client.VideoData(
        url="https://example.org/fictional-product-demo",
        title="DEMO ONLY — synthetic API engineering talk",
        lang="en",
        segments=(
            sdk_client.Segment("Today we introduce a searchable research vault.", 0, 4000),
            sdk_client.Segment("A transcript can help researchers find relevant explanations.", 4000, 5500),
            sdk_client.Segment("Full text search returns matching videos and an excerpt.", 9500, 5000),
        ),
        transcript=("Today we introduce a searchable research vault.\n"
                    "A transcript can help researchers find relevant explanations.\n"
                    "Full text search returns matching videos and an excerpt."),
    )


def ingest_one(db, client, url: str, options, *, title: str | None = None) -> str:
    video = sdk_client.fetch_video(
        client, url, mode=options.mode, lang=options.lang,
        title=title, metadata=options.metadata,
        interval=options.interval, max_wait=options.max_wait,
    )
    return store.upsert(db, video)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive")
    if getattr(args, "interval", 1) <= 0 or getattr(args, "max_wait", 1) <= 0:
        parser.error("--interval and --max-wait must be positive")

    with closing(store.connect(args.db)) as db:
        if args.command == "init":
            print(f"Ready: {args.db.resolve()}")
        elif args.command == "demo":
            key = store.upsert(db, fake_example(), source_kind="synthetic_demo")
            print(f"Created synthetic example: {key} (NO API call was made)")
        elif args.command in ("add", "add-file"):
            api_key = os.getenv("SUPADATA_API_KEY", "").strip()
            try:
                client = sdk_client.create_sdk_client(api_key)
            except sdk_client.IngestionError as error:
                print(f"Error: {error}", file=sys.stderr)
                return 2
            if args.command == "add":
                urls = [args.url]
            else:
                try:
                    urls = [x.strip() for x in args.path.read_text(encoding="utf-8").splitlines()
                            if x.strip() and not x.strip().startswith("#")]
                except OSError as error:
                    print(f"Error reading input file: {error}", file=sys.stderr)
                    return 2
            if not urls:
                print("No video URLs found", file=sys.stderr)
                return 2
            failures = 0
            for url in urls:
                print(f"Importing: {url}")
                try:
                    key = ingest_one(
                        db, client, url, args,
                        title=getattr(args, "title", None),
                    )
                    print(f"  Saved video {key}")
                except Exception as error:
                    failures += 1
                    print(f"  Import failed: {error}", file=sys.stderr)
            if failures:
                print(f"Failed: {failures}/{len(urls)}", file=sys.stderr)
                return 1
        elif args.command == "list":
            videos = store.list_videos(db)
            if not videos:
                print("Vault is empty. Try: python -m research_vault demo")
            for row in videos:
                print(f"{row['id']}  [{row['lang']}]  {row['title']}")
        elif args.command == "search":
            try:
                results = store.search(db, args.query, args.limit)
            except Exception as error:
                print(f"Search failed: {error}", file=sys.stderr)
                return 1
            if not results:
                print("No matches")
            for row in results:
                print(f"{row['id']}  {row['title']}\n  {row['url']}\n  {row['excerpt']}\n")
        elif args.command == "show":
            row = store.by_id(db, args.id)
            if row is None:
                print("Video not found", file=sys.stderr)
                return 1
            print(exporter.note_text(db, row)[:2000])
        elif args.command == "stats":
            for k, v in store.stats(db).items():
                print(f"{k}: {v}")
        elif args.command == "export":
            if args.id:
                row = store.by_id(db, args.id)
                if row is None:
                    print("Video not found", file=sys.stderr)
                    return 1
                rows = [row]
            else:
                rows = store.list_videos(db, limit=1000000)
            for row in rows:
                filename = exporter.export_video(db, row, args.dir, args.format)
                print(f"Exported: {filename}")
            if not rows:
                print("Vault is empty")
    return 0
