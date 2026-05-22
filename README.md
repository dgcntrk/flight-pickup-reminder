# Flight Pickup Reminder

Flight Pickup Reminder is a small FastAPI service that calculates when a driver should leave for an airport pickup, then escalates reminders until accepted proof arrives.

It combines flight ETA, traffic-aware drive time, outbound calls, Telegram live-location proof, optional photo proof, and an auditable state log. The default configuration is dry-run safe: it will not place calls unless `CALLING_ENABLED=true` and live Twilio credentials are configured.

## Why It Exists

Airport pickups are timing-sensitive and easy to fumble: flight ETAs move, traffic changes, and a reminder that fires too early or too late is not very useful. This project turns that into a simple plan:

```text
leave_by = arrival_eta - route_duration - airport_buffer
call_start_at = leave_by - call_lead
```

Once the call window opens, the service alternates through configured recipients until someone shares accepted proof or the maximum attempt count is reached.

## Features

- Polls FlightAware AeroAPI for the configured flight.
- Polls Google Routes API for traffic-aware drive duration.
- Supports manual arrival fallback when FlightAware is unavailable.
- Computes `leave_by` and `call_start_at`.
- Alternates reminder calls through Twilio.
- Accepts Telegram live-location proof through polling or webhook.
- Optionally accepts MMS/photo replies through a Twilio webhook.
- Optionally accepts Telegram proof photos/documents.
- Checks image EXIF for Apple/iPhone camera evidence and recency.
- Uses OpenAI vision for optional photo proof.
- Supports `STOP` by SMS to opt out immediately.
- Provides `/status`, `/config-check`, `/tick`, and mock endpoints for rehearsal.

## Safety And Consent

Use this only with explicit consent from every person being called, texted, asked to share location, or asked to send proof photos. Repeated calls, live-location checks, and image proof can become invasive or legally sensitive if used casually.

Telegram live location is stronger than a static map pin for this workflow, but it still depends on consent and trust. Static map pins can be spoofed, so the recommended live setup keeps `PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=true`.

See [SECURITY.md](SECURITY.md) before running this with real people or real credentials.

## Setup

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` with your own values:

- `FLIGHT_IDENT`: exact airline flight identifier, for example `F8701` or an ICAO-style ident.
- `FLIGHT_LOCAL_DATE`: local date of the flight.
- `FRIENDS_ADDRESS`: exact pickup starting address.
- `AIRPORT_ADDRESS`: destination airport address.
- `RECIPIENT_NUMBERS`: comma-separated E.164 numbers, for example `+16045550101,+16045550102`.
- `PUBLIC_BASE_URL`: public HTTPS URL for Twilio or Telegram webhooks.
- `TELEGRAM_BOT_TOKEN`: Telegram proof bot token.
- `TELEGRAM_ALLOWED_USER_IDS`: comma-separated numeric Telegram sender IDs.
- API keys for FlightAware, Google Maps, and Twilio. OpenAI is only needed for optional photo proof fallback.

For local webhook testing:

```sh
ngrok http 8000
```

Set Twilio's Messaging webhook to:

```text
https://YOUR_PUBLIC_HOST/webhooks/twilio/inbound
```

No inbound voice webhook is required. The app attaches call instructions and status callbacks when it creates outbound calls.

## Run

```sh
. .venv/bin/activate
python -m flight_pickup_reminder
```

Open:

```text
http://127.0.0.1:8000/status
```

Trigger one manual poll:

```sh
curl -X POST http://127.0.0.1:8000/tick
```

## Test Without Paid APIs

Run the included mock environment:

```sh
. .venv/bin/activate
ENV_FILE=.env.mock python -m flight_pickup_reminder
```

Then exercise the flow:

```sh
curl -s http://127.0.0.1:8000/config-check | python -m json.tool
curl -s -X POST http://127.0.0.1:8000/mock/reset | python -m json.tool
curl -s -X POST 'http://127.0.0.1:8000/mock/tick-at?now=2026-05-16T16:15:00Z' | python -m json.tool
curl -s -X POST http://127.0.0.1:8000/mock/proof/accept | python -m json.tool
```

The app uses `DEFAULT_DRIVE_MINUTES` and logs dry-run call attempts into `data/mock-state.json`.

## Useful Endpoints

- `GET /health`: health check.
- `GET /status`: current state, latest plan, proof status, and recent events.
- `GET /config-check`: missing settings and safety warnings.
- `POST /tick`: fetch flight/route data and evaluate the reminder plan.
- `POST /telegram/poll`: manually poll Telegram for proof messages.
- `POST /mock/reset`: reset mock state when `MOCK_ENABLED=true`.
- `POST /mock/tick-at?now=...`: evaluate a mock tick at a fixed time.

## Docs

- [API credential guide](API_CREDENTIALS_GUIDE.md)
- [Example runbook](MORNING_RUNBOOK.md)
- [Security policy](SECURITY.md)

## Tests

```sh
pytest -q
```

The test suite covers planning, orchestration, state persistence, readiness checks, Twilio behavior, Telegram intake, and proof evaluation.

## Provider References

- FlightAware AeroAPI: https://www.flightaware.com/commercial/aeroapi/faq.rvt
- Google Routes API: https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
- Twilio outbound calls: https://www.twilio.com/docs/voice/api/call
- Twilio MMS webhooks: https://www.twilio.com/docs/messaging/guides/webhook-request
- Telegram Bot API: https://core.telegram.org/bots/api
- OpenAI image inputs: https://developers.openai.com/api/docs/guides/images-vision
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
