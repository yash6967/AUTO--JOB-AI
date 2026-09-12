# Auto Job AI

A terminal-first job application agent built with LangGraph. It discovers jobs, parses requirements, scores fit against a normalized resume, requests human approval through Telegram, tracks decisions in Notion, and supports opt-in email or Playwright submission.

## Current Status

Implemented and tested:

- LangGraph orchestration with persistent SQLite checkpoints
- Shared multi-job queue state
- Resume normalization for JSON, PDF, DOCX, TXT, and Markdown
- Greenhouse board discovery through the Greenhouse API
- Standard and custom Greenhouse URL support
- Lever API routing
- Playwright fallback for generic job pages
- Pydantic structured job-requirements parsing
- Groq requirements parsing, fit scoring, and tailoring when configured
- Deterministic fallbacks for offline runs and malformed Groq responses
- Match threshold routing and automatic queue continuation
- Telegram approval messages with Approve & Apply and Skip buttons
- FastAPI Telegram webhook for checkpoint resumption
- Notion application tracking
- Dry-run, SMTP email, and Playwright submission modes
- Structured application confirmations and persistent error logs
- Mocked integration and graph tests

The current test suite contains 25 tests.

## Requirements

- Python 3.11+
- A virtual environment
- API credentials for live providers
- A public HTTPS URL for the Telegram webhook, such as an ngrok tunnel

## Setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

For generic-page Playwright extraction or form submission, install the browser once:

```bash
.venv/bin/playwright install chromium
```

Copy the environment template and fill in only the services you intend to use:

```bash
cp .env.example .env
```

Never commit `.env` or paste active credentials into chat or source control. Rotate credentials that have been exposed.

## Environment Variables

```env
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
EXA_API_KEY=
JSEARCH_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
AGENT_DATABASE=runtime/agent.sqlite
NOTION_TOKEN=
NOTION_DATABASE_ID=
SUBMISSION_MODE=dry_run
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
```

`NOTION_DATABASE_ID` must be the database ID, not the parent page ID. The database must be shared with the Notion integration. The current tracker expects these database properties:

- `Job Title` - title
- `Company` - rich text
- `Match Score` - number
- `Status` - status
- `Date Added` - date
- `Job URL` - URL

Valid application status mappings are `Approved`, `Applied`, `Rejected`, and `Discovered`.

## Run Tests

```bash
.venv/bin/python -m pytest -q
```

The expected result is currently:

```text
25 passed
```

## Offline CLI Smoke Test

This uses deterministic mock jobs and does not call Greenhouse, Groq, Telegram, or Notion:

```bash
.venv/bin/python main.py \
  --database /tmp/auto-job-ai-smoke.sqlite \
  --thread-id smoke-run
```

Expected behavior:

- 2 jobs discovered
- 1 low-score job skipped
- 1 job pending approval
- The CLI prints `Waiting for mobile approval...`
- The run exits with a persisted checkpoint

## Real Greenhouse and Groq Run

Use `--max-jobs 1` for a controlled first run:

```bash
rm -f /tmp/auto-job-ai-real.sqlite

.venv/bin/python main.py \
  --greenhouse-board-url https://boards.greenhouse.io/stripe \
  --max-jobs 1 \
  --database /tmp/auto-job-ai-real.sqlite \
  --thread-id real-run-1
```

The run discovers and normalizes Greenhouse listings, routes the active job, parses requirements, scores the candidate, prepares materials, sends Telegram approval, and pauses before submission.

`--greenhouse-board-url` can be repeated for multiple boards. `--max-jobs` is useful for limiting provider and Groq usage during testing.

## Telegram Approval Flow

The CLI and webhook are separate processes. The webhook must use the exact same SQLite database path as the CLI.

### Terminal 1: Start the webhook

```bash
cd /Users/shreyas/Desktop/CODE/LEMMA/AUTO--JOB-AI

AGENT_DATABASE=/tmp/auto-job-ai-real.sqlite \
.venv/bin/uvicorn server.webhook:app --host 0.0.0.0 --port 8000
```

Telegram cannot reach `localhost` directly. Start a public HTTPS tunnel in another terminal:

```bash
ngrok http 8000
```

Register the public URL with Telegram:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://YOUR-TUNNEL-DOMAIN/telegram/webhook"
```

### Terminal 2: Start the job run

```bash
.venv/bin/python main.py \
  --greenhouse-board-url https://boards.greenhouse.io/stripe \
  --max-jobs 1 \
  --database /tmp/auto-job-ai-real.sqlite \
  --thread-id telegram-run-1
```

The CLI exits after sending the approval message. Click Approve & Apply or Skip in Telegram. Telegram sends the compact callback to the webhook, which loads the checkpoint, updates `human_decision`, resumes the graph, and continues the queue.

The callback contains the thread ID, while the webhook retrieves the active job from the checkpoint. This keeps Telegram callback data below Telegram's 64-byte limit.

Standalone Telegram delivery test:

```bash
.venv/bin/python main.py --telegram-test
```

## Notion Smoke Test

Create a test row without running the job graph:

```bash
.venv/bin/python main.py --notion-test
```

A successful result includes `notion_ok: true` and a created `page_id`.

## Submission Modes

Approved jobs default to safe dry-run behavior:

```env
SUBMISSION_MODE=dry_run
```

Dry-run records the job as applied and creates a confirmation block without sending an application.

For email submission:

```env
SUBMISSION_MODE=email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=...
```

The job must contain `application_email`. Use email mode only after testing with dry-run.

For web-form submission:

```env
SUBMISSION_MODE=playwright
```

Playwright maps standard contact fields, fills a cover letter, uploads `tailored_materials["resume_pdf"]` when available, and submits the form. Form selectors vary by site and may require provider-specific work.

## Output and Error State

After approval and successful dispatch, state includes a confirmation block similar to:

```json
{
  "status": "applied",
  "message": "Application submitted successfully.",
  "job_title": "Backend Engineer",
  "company": "Example Company",
  "url": "https://example.com/job",
  "submitted_at": "2026-09-12T12:00:00+00:00",
  "channel": "dry_run"
}
```

Submission and tracking failures are retained in `error_logs` with:

- timestamp
- component
- channel when applicable
- job URL and title
- exception type
- error message

The state is persisted through the LangGraph SQLite checkpoint.

## Project Layout

```text
agent/       LangGraph state, nodes, and graph construction
assets/      Normalized resume and source assets
server/      Telegram webhook and operational documentation
tests/       Unit and mocked integration tests
tools/       Greenhouse, Lever, Groq, Notion, submission, and resume helpers
main.py      CLI entry point
plan.md      Architecture and milestone plan
progress.md  Detailed implementation checklist
```

## Remaining Work

- Exa and JSearch provider execution
- ATS-formatted PDF generation
- Updating existing Notion rows after submission
- More robust provider-specific Playwright form mappings
- Mocked Playwright form tests
- Persistent checkpoint recovery test across a process restart
- Broader malformed provider and resume validation coverage
- Python 3.11 and 3.12 compatibility verification
