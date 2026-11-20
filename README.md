# Video Research Vault — searchable transcripts with the official Supadata Python SDK

**Collect video transcripts, search them locally, and export timestamped Markdown or JSON notes.** Powered by the [Supadata Python SDK](https://github.com/supadata-ai/py). Local database storage and full-text search run without any cloud indexing service, background worker, or LLM.

[![Offline tests](https://github.com/hubao201198/supadata-research-vault/actions/workflows/tests.yml/badge.svg)](https://github.com/hubao201198/supadata-research-vault/actions/workflows/tests.yml)

**[Get started with Supadata](https://supadata.ai/r/9YW9BZ05)** · [Supadata API docs](https://docs.supadata.ai/get-transcript)

> **Disclosure:** This is my personal referral link. I may receive Supadata API credits if this open-source project qualifies for a promotional reward. This project is independent, and the examples do not imply an endorsement by Supadata.

## Why build this?

Developer talks, conference presentations, product demos, tutorials, and long-form video interviews contain useful information. But once a week of watching is over, the details are hard to recall. Searching a collection of spoken explanations with a normal filesystem does not work well. Manually copying captions into Markdown files is error prone and does not preserve source attribution or precise timestamps.

Video Research Vault is a small, testable, local-first tool for this problem. It asks the **official Supadata SDK** for a transcript, handles immediate and asynchronous responses, stores the transcript in SQLite with source URL, language, and segment time offsets, and creates a full-text-search index. A user can then find which of their saved videos discusses a term, inspect the result, or export the associated notes to a folder. It works with publicly accessible videos supported by Supadata: YouTube, TikTok, Instagram Reels, X, and other compatible sources.

**This is a usable application, not just a tutorial:** there is a command-line interface, a persistence layer, a search implementation, optional metadata enrichment, an offline demo, tests, and GitHub Actions.

## See it work in 20 seconds — completely offline

The following example **does not call Supadata and does not use any credits**. Its transcript is clearly labeled synthetic so anyone can test local search and export before entering a key.

```bash
# Python 3.10+; from the repository root
python3 -m research_vault demo
python3 -m research_vault list
python3 -m research_vault search "research"
python3 -m research_vault export --format md --dir notes
```

Example console output from the offline demo:

```text
Created synthetic example: <stable-id> (NO API call was made)
<stable-id>  [en]  DEMO ONLY — synthetic API engineering talk

<stable-id>  DEMO ONLY — synthetic API engineering talk
  https://example.org/fictional-product-demo
  [research] vault.

Exported: notes/DEMO-ONLY-synthetic-API-engineering-talk-<stable-id>.md
```

See the committed [synthetic example note](examples/demo-note.md). You can open the exported Markdown and see the original source URL, language, import time, and time offsets such as `[00:04]`. The timestamps in the demo are fixture data; real timestamps come from Supadata's returned transcript chunks. **This is not presented as a live API response.**

## Installation for real Supadata ingestion

The official SDK accepts a secret API key using `Supadata(api_key=...)`. The recommended setup uses a virtual environment and an environment variable:

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .           # installs the pinned official SDK and CLI
export SUPADATA_API_KEY="YOUR_SUPADATA_API_KEY"   # PowerShell: $env:SUPADATA_API_KEY = "..."
```

Get an API key in the [Supadata dashboard](https://dash.supadata.ai/). Never commit the key or paste it into a GitHub issue.

**Important SDK version detail:** as checked on 2026-11-20, the [published PyPI package](https://pypi.org/project/supadata/) lists 1.6.0, but [Supadata's official Python documentation](https://docs.supadata.ai/integrations/python) says the transcript asynchronous job-status method requires 1.7.0+. Therefore `requirements.txt` pins the **official SDK Git repository** at a specific 1.7.0 commit (`35b369f…`), not a fabricated PyPI version. This makes `client.transcript.get_job_status(job_id)` available while preserving reproducibility. When a compatible SDK becomes available on PyPI, the pin can be updated.

## Ingest a real public video

```bash
# Native captions only by default — avoids accidental AI transcription fallback.
python -m research_vault add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --title "Example talk"

# Ask the SDK for metadata and request an English caption track if available.
python -m research_vault add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --metadata --lang en

# Accept generation as a fallback only if you choose the additional credit costs.
python -m research_vault add "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --mode auto

# Process a text file of URLs, one URL per line; failed entries do not stop later items.
python -m research_vault add-file examples/urls.txt --mode native
```

For the list example, first replace the commented placeholders in `examples/urls.txt` with URLs you are entitled to access and use. If you installed the project with `pip install -e .`, you may use `research-vault` instead of `python -m research_vault`. Each `add` command sends a real request through the official SDK. `--metadata` is optional and makes another SDK call for a better title. If you do not provide a title or request metadata, the app builds a descriptive fallback from the URL; it does not invent the real video title.

### The real SDK integration

The application uses the following concrete APIs in [`research_vault/sdk_client.py`](research_vault/sdk_client.py):

```python
from supadata import Supadata

client = Supadata(api_key=api_key)
result = client.transcript(url=video_url, text=False, mode="native")

if hasattr(result, "content"):
    transcript = result
else:
    job = client.transcript.get_job_status(result.job_id)
    # Repeat at bounded intervals until completed or failed.
    if job.status == "completed":
        transcript = job.result
```

The complete function `resolve_transcript` implements **bounded polling** for `queued` and `active`, a terminal `failed` branch, a nonempty-result check, and a configurable timeout. If the job finishes, the returned `Transcript` object is converted into our typed `Segment` records and written to the local database. On import, a video ID is deterministically computed from its URL. Re-ingesting the same URL updates its stored transcript and FTS index instead of creating duplicates.

Why use `text=False`? Supadata returns individual chunks with `text`, `offset`, and `duration`, where timings are measured in **milliseconds**. Keeping those offsets supports clickable references in a future UI and makes the Markdown notes more useful than plain text. A plain-text response can also be handled, but no fake timestamp is assigned to it.

## Search, inspect, and export

```bash
python -m research_vault search "memory"
python -m research_vault search "language model" --limit 5
python -m research_vault list
python -m research_vault show <video-id>
python -m research_vault stats
python -m research_vault export --format md --dir notes
python -m research_vault export --format json --dir notes
python -m research_vault export --id <video-id> --format md --dir notes
```

Search happens locally in **SQLite FTS5**, not at Supadata and not at an LLM provider. The database stores URL, title, detected language, transcript, individual timestamped segments and an import time. Results include matching video titles, source URLs and a highlighted excerpt. Search input is treated as plain terms, joined with AND, rather than being interpolated as untrusted SQL or arbitrary FTS operators. The app currently does **keyword retrieval**, not semantic similarity search. No chat or invented summary is offered as though it were extracted directly from the video.

Exported Markdown resembles the following. This is a **synthetic fixture example**, not a claim about a real video:

```markdown
# DEMO ONLY — synthetic API engineering talk

- Source: https://example.org/fictional-product-demo
- Language: en
- Source kind: synthetic_demo

## Transcript

**[00:00]** Today we introduce a searchable research vault.

**[00:04]** A transcript can help researchers find relevant explanations.

**[00:09]** Full text search returns matching videos and an excerpt.
```

An actual exported file will additionally include its UTC import timestamp, and its segments will come from a real SDK response. Export formats are `.md` and `.json`. This is a deliberately local project: results go into `vault.db` (ignored by Git), and generated notes go into `notes/` (also ignored). Neither file is uploaded by the application.

## Project map

```text
supadata-research-vault/
├── README.md
├── pyproject.toml                 # installable CLI: research-vault
├── requirements.txt               # official Supadata SDK, pinned Git revision
├── research_vault/
│   ├── sdk_client.py              # REAL SDK transcript and async polling calls
│   ├── store.py                   # SQLite schema, FTS5, upserts and search
│   ├── exporter.py                # timestamped Markdown and JSON
│   ├── cli.py                     # init/demo/add/add-file/search/list/show/export
│   └── __main__.py
├── tests/                          # offline mocked-SDK integration tests
├── examples/
│   ├── urls.txt
│   └── demo-note.md              # explicitly synthetic exported fixture
├── .github/workflows/tests.yml
├── .gitignore
└── LICENSE
```

## Tests and engineering choices

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q research_vault tests
```

Tests cover real SDK call signatures using a fake client, asynchronous transitions, job failure, missing transcript, metadata normalization, milliseconds, FTS search, deduplicating imports, Markdown and JSON file generation, batch-file partial failure, and end-to-end CLI execution with a fake SDK. This lets reviewers validate the app without spending credits. They do **not** establish that Supadata's remote service is reachable or that a particular third-party video is accessible right now. For a full smoke test, set your own API key and run an `add` command on an eligible public video.

The default `--mode native` is intentional. [Supadata's current API docs](https://docs.supadata.ai/get-transcript#pricing) indicate **1 credit for a native transcript**, whereas AI-generated transcription costs **2 credits per minute**. An unavailable transcript can incur a credit. Job-status polling itself does not incur extra credits. `--mode auto` can fall back to paid generation; do not use it across hundreds of videos without first understanding costs. The API accepts only supported public, accessible media. Obey the source platform's terms and creators' copyright.

## Known limitations and roadmap

- **No live API test is claimed.** The repository ships unit tests and a synthetic no-key demo; remote integration requires a personal key and accessible public video.
- Only completed videos are supported. Private, age-restricted, geoblocked and live streams may fail. Network and quota errors are surfaced; there is no silent credit-consuming fallback.
- The app performs synchronous sequential ingestion. It does not include a multi-process job scheduler or a web server; this keeps review, auditing and cost control straightforward.
- Markdown is for personal research. If you redistribute transcript contents, check permissions and applicable rights.
- For very large collections, future versions could add a background job queue, local vector indexing, source thumbnails, and a searchable web UI. None of those are claimed as implemented here.

**Built using the official [Supadata Python SDK](https://github.com/supadata-ai/py)** · [Get an API key or try Supadata through my disclosed referral link](https://supadata.ai/r/9YW9BZ05).

Licensed under [MIT](LICENSE). Contributions and bug reports welcome.
