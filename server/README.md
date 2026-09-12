# Telegram Webhook

Start the webhook from the repository root with:

```bash
.venv/bin/uvicorn server.webhook:app --host 0.0.0.0 --port 8000
```

Set `AGENT_DATABASE` to the same SQLite checkpoint path used by the CLI. Configure
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`, then register the public
webhook URL with Telegram's `setWebhook` API.

To test Telegram delivery separately from the job graph:

```bash
.venv/bin/python main.py --telegram-test
```

This sends one labeled test approval message with the Approve and Skip buttons.
