# Telegram Webhook

Start the webhook from the repository root with:

```bash
.venv/bin/uvicorn server.webhook:app --host 0.0.0.0 --port 8000
```

Set `AGENT_DATABASE` to the same SQLite checkpoint path used by the CLI. Configure
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`, then register the public
webhook URL with Telegram's `setWebhook` API.

For a real run, use two terminals. Start the webhook first, using the same
database path as the CLI:

Terminal 1:

```bash
AGENT_DATABASE=/tmp/auto-job-ai-telegram-e2e.sqlite \
.venv/bin/uvicorn server.webhook:app --host 0.0.0.0 --port 8000
```

The webhook process must be restarted whenever `AGENT_DATABASE` changes. A
callback for a thread stored in a different database cannot resume the run.

Terminal 2:

```bash
rm -f /tmp/auto-job-ai-telegram-e2e.sqlite
.venv/bin/python main.py \
	--greenhouse-board-url https://boards.greenhouse.io/stripe \
	--max-jobs 1 \
	--database /tmp/auto-job-ai-telegram-e2e.sqlite \
	--thread-id telegram-e2e-3
```

The CLI exits after sending the approval message. That is expected. Keep
Terminal 1 running; clicking the Telegram button sends a callback to the public
webhook, which resumes the saved checkpoint and performs the decision.
The webhook response includes the decision, applied/skipped counts, the
`confirmation` block, and any `error_logs` produced by submission or Notion.

To test Telegram delivery separately from the job graph:

```bash
.venv/bin/python main.py --telegram-test
```

This sends one labeled test approval message with the Approve and Skip buttons.

To test Notion tracking separately from the job graph:

```bash
.venv/bin/python main.py --notion-test
```

This creates one page titled `Notion integration test` in `NOTION_DATABASE_ID`.
`NOTION_DATABASE_ID` must be the database ID, not the ID of the page containing
the database. The database must also be shared with the Notion integration.

## Milestone 6

Notion tracking is enabled by the CLI when both `NOTION_TOKEN` and
`NOTION_DATABASE_ID` are set. Approved jobs use `SUBMISSION_MODE`, which defaults
to `dry_run`. Set it to `email` with `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
and `SMTP_PASSWORD`, or set it to `playwright` for web-form dispatch.

With `SUBMISSION_MODE=dry_run`, clicking Approve & Apply does not fill a job
form or send an application. It verifies the approval, checkpoint, tracking,
and state flow only.

Email jobs must include `application_email`. A resume PDF can be supplied through
`tailored_materials["resume_pdf"]` before dispatch.

After an approved dry-run or real submission, the CLI includes a `confirmation`
block with the job, timestamp, and channel. Submission or Notion failures are
retained in the `error_logs` block with the component, exception type, message,
job URL, and timestamp.
