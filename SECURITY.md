# Security Policy

This project can place phone calls, receive webhooks, process live locations, and optionally evaluate proof photos. Treat it as a consent-first personal automation tool, not a surveillance product.

## Before Running Live

- Get explicit consent from every recipient before enabling calls, texts, live-location proof, or photo proof.
- Keep `CALLING_ENABLED=false` until `/config-check` is clean.
- Keep `PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=true` if using Telegram proof; static pins are easier to spoof.
- Restrict API keys where possible, especially Google Maps and Twilio credentials.
- Use `TELEGRAM_ALLOWED_USER_IDS` for live use. Do not leave Telegram sender access open.
- Leave Twilio webhook signature validation enabled unless you are deliberately testing locally.

## Secrets

Never commit `.env`, runtime logs, `data/*.json`, proof images, tunnel URLs, phone numbers, Telegram sender IDs, or bot tokens. The `.gitignore` excludes these by default.

If a token, API key, phone number, or sender ID is exposed in a public repo, rotate the credential immediately and remove it from git history before re-publishing.

## Reporting

If you find a security issue, open a private report with enough detail to reproduce the problem. Avoid posting live credentials, personal phone numbers, locations, or proof media in issues.
