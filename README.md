##DEMO VIDEO:
https://www.loom.com/share/719654cc7eb8465caac3d0275bd51e4a


# Auto Job AI

A terminal-first job application agent built with LangGraph. It discovers jobs, parses requirements, scores fit against a normalized resume, requests human approval through Telegram, tracks decisions in Notion, and supports opt-in email or Playwright submission.

## Current Status

Implemented and tested:

- LangGraph orchestration with persistent SQLite checkpoints
- Shared multi-job queue state
- Resume normalization for JSON, PDF, DOCX, TXT, and Markdown
- Greenhouse board discovery through the Greenhouse API
- Optional Exa web search filtered to public Greenhouse job URLs
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
- Authenticated Greenhouse candidate-browser flow with persistent local session
- Automatic staging for matches above the configured score and second Telegram submit confirmation
- Structured application confirmations and persistent error logs
- Mocked integration and graph tests

The current test suite contains 26 tests.

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
GREENHOUSE_AUTO_APPLY_SCORE=90
GREENHOUSE_BROWSER_PROFILE=runtime/greenhouse-browser
GREENHOUSE_LOGIN_WAIT_SECONDS=120
GREENHOUSE_POST_SUBMIT_HOLD_SECONDS=0
```

For the Greenhouse candidate flow on macOS:

```env
SUBMISSION_MODE=greenhouse
GREENHOUSE_AUTO_APPLY_SCORE=90
GREENHOUSE_BROWSER_PROFILE=runtime/greenhouse-browser
GREENHOUSE_LOGIN_WAIT_SECONDS=120
```

The candidate profile and infrequently changing application answers live in
`assets/application_profile.json`. Edit that file or pass a replacement with
`--application-profile`. It intentionally contains blank demo values until you
fill in your own details.

The CLI automatically uploads the only PDF found in `assets`. To choose a
different file explicitly, use `--resume-pdf path/to/resume.pdf`.

For debugging Greenhouse email verification or OTP challenges, set
`GREENHOUSE_POST_SUBMIT_HOLD_SECONDS=300` for the CLI run. After the final
Telegram submit action, the visible browser remains open for five minutes and
the terminal prints the current page text while you enter the code manually.

When `EXA_API_KEY` is present, the run also searches the public web for
Greenhouse listings using the configured roles and locations. Results are
filtered to `boards.greenhouse.io` and deduplicated with configured boards.

On the first Greenhouse run, Chromium opens the candidate portal using a
persistent local profile. Complete login, MFA, and any CAPTCHA yourself. The
password is not read by or stored in this application. The session is reused on
later runs from `GREENHOUSE_BROWSER_PROFILE`.

Jobs scoring above 90 are staged automatically. Telegram receives a review
message with the captured application screenshot and a `Submit application`
button. The form is submitted only after that second Telegram confirmation.
Unknown required questions, MFA, CAPTCHA, and missing resume uploads stop the
application and are reported as manual fields instead of being guessed.

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
26 passed
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

Telegram cannot reach `localhost` directly. Use ngrok to expose the local webhook
through a temporary public HTTPS URL.

### Install and start ngrok

Install ngrok from [ngrok.com/download](https://ngrok.com/download), then authenticate it with your ngrok account if prompted:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Start the tunnel in another terminal:

```bash
ngrok http 8000
```

ngrok will display a forwarding address similar to:

```text
Forwarding https://example-name.ngrok-free.app -> http://localhost:8000
```

Copy the HTTPS address. Keep this ngrok terminal running while testing. The URL
can change when ngrok restarts unless you use a reserved domain.

Register the public URL with Telegram:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://YOUR-TUNNEL-DOMAIN/telegram/webhook"
```

For example:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://example-name.ngrok-free.app/telegram/webhook"
```

Verify the registered webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

The response should show your ngrok URL in `result.url` and a recent
`last_error_message` should be absent. If the ngrok URL changes, call
`setWebhook` again with the new URL.

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

Greenhouse mode is the provider-specific alternative: it uses labels and
required-field checks, captures a review screenshot, and requires a separate
final confirmation before clicking the submit control.

## Verify Submission Results

The webhook terminal logs a callback result after Telegram approval. A `200 OK`
means the callback was handled; it does not by itself prove submission success.

Inspect the checkpoint directly:

```bash
.venv/bin/python -c "from agent.graph import build_graph, checkpoint_config; graph, connection = build_graph('/tmp/auto-job-ai-playwright.sqlite'); state = graph.get_state(checkpoint_config('playwright-test-1')).values; print({'status': state.get('status'), 'confirmation': state.get('confirmation'), 'error_logs': state.get('error_logs', []), 'last_event': state.get('processing_log', [])[-1] if state.get('processing_log') else None}); connection.close()"
```

Successful Playwright submission:

```text
confirmation.channel = "playwright"
```

Playwright ran but failed:

```text
error_logs[0].component = "submission"
error_logs[0].channel = "playwright"
```

The current generic Playwright implementation can fail when a job site does
not contain `button[type='submit']` or `input[type='submit']`. In that case the
error log contains the selector timeout and the application is not marked as
successfully submitted.

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
