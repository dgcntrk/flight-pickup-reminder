# Example Live Runbook

Use this as a checklist before enabling real calls. Keep `CALLING_ENABLED=false` until the dry run, credentials, recipients, and consent are all confirmed.

## Mock Rehearsal

Run everything without paid APIs:

```sh
. .venv/bin/activate
ENV_FILE=.env.mock python -m flight_pickup_reminder
```

In another terminal:

```sh
curl -s http://127.0.0.1:8000/config-check | python -m json.tool
curl -s -X POST http://127.0.0.1:8000/mock/reset | python -m json.tool
curl -s -X POST 'http://127.0.0.1:8000/mock/tick-at?now=2026-05-16T16:15:00Z' | python -m json.tool
curl -s -X POST http://127.0.0.1:8000/mock/proof/accept | python -m json.tool
curl -s -X POST 'http://127.0.0.1:8000/mock/tick-at?now=2026-05-16T16:15:31Z' | python -m json.tool
```

Expected result:

- The forced `tick-at` records one dry-run call.
- `/mock/proof/accept` sets `proof_accepted=true`.
- The next `tick-at` skips calls with reason `proof_accepted`.

## Live Setup Checklist

1. Copy the live env:

```sh
cp .env.example .env
```

2. Fill these first:

```env
FLIGHT_IDENT=
FLIGHT_LOCAL_DATE=YYYY-MM-DD
FRIENDS_ADDRESS=
AIRPORT_ADDRESS=
RECIPIENT_NUMBERS=
TELEGRAM_ALLOWED_USER_IDS=
```

3. Configure Twilio with calls still disabled:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_API_KEY_SID=
TWILIO_API_KEY_SECRET=
TWILIO_FROM_NUMBER=
CALLING_ENABLED=false
```

If you use a Twilio API Key SID/secret, you still need the account `TWILIO_ACCOUNT_SID` that starts with `AC`. Keep `TWILIO_AUTH_TOKEN` if webhook signature validation is enabled.

4. Start a public tunnel if running locally:

```sh
ngrok http 8000
```

Set:

```env
PUBLIC_BASE_URL=https://YOUR_PUBLIC_URL
```

Configure Twilio's Messaging webhook:

```text
https://YOUR_PUBLIC_URL/webhooks/twilio/inbound
```

5. Confirm Telegram bot access:

Ask each recipient to send `/start` to your bot, then run:

```sh
curl -s -X POST http://127.0.0.1:8000/telegram/poll | python -m json.tool
curl -s http://127.0.0.1:8000/status | python -m json.tool | grep sender_id
```

Set the IDs:

```env
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
TELEGRAM_POLLING_ENABLED=true
```

Restart after editing `.env`.

6. Add Telegram live-location proof and Google Routes:

```env
GOOGLE_MAPS_API_KEY=
PROOF_ACCEPT_TELEGRAM_LOCATION=true
PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=true
TELEGRAM_LOCATION_MAX_AGE_MINUTES=10
TELEGRAM_LOCATION_MAX_ACCURACY_METERS=1500
PROOF_MOCK_MODE=off
```

7. Add FlightAware or a manual arrival fallback:

```env
FLIGHTAWARE_API_KEY=
MANUAL_ARRIVAL_ISO=
```

If FlightAware is not ready, use manual ETA:

```env
MANUAL_ARRIVAL_ISO=2026-05-16T10:00:00-07:00
```

Replace the timestamp with the actual live arrival estimate.

8. Start live dry-run:

```sh
. .venv/bin/activate
python -m flight_pickup_reminder
```

9. Check readiness:

```sh
curl -s http://127.0.0.1:8000/config-check | python -m json.tool
```

10. Trigger one poll:

```sh
curl -s -X POST http://127.0.0.1:8000/tick | python -m json.tool
```

Confirm:

- `last_error` is `null`.
- `plan.leave_by` is reasonable.
- `plan.call_start_at` is before `plan.leave_by`.
- `route.provider` is `google_routes` if Google is configured.
- `flight.provider` is `flightaware` if FlightAware is configured, otherwise `manual`.

11. Enable real calls only after the above works:

```env
CALLING_ENABLED=true
MOCK_ENABLED=false
PROOF_MOCK_MODE=off
```

Restart:

```sh
python -m flight_pickup_reminder
```

## Fast Fallbacks

If FlightAware is not ready:

- Use `MANUAL_ARRIVAL_ISO` and update it manually from airline or airport status.

If Google Maps is not ready:

- Set `DEFAULT_DRIVE_MINUTES` conservatively high.

If OpenAI or EXIF blocks proof:

- Prefer Telegram live location with `PROOF_ACCEPT_TELEGRAM_LOCATION=true`.
- If you still use photo fallback, temporarily set `PROOF_REQUIRE_IPHONE_EXIF=false`.
- Keep `PROOF_MOCK_MODE=off` for live use unless you are deliberately bypassing proof checks.

If Telegram proof does not appear:

- Confirm recipients shared live location with your bot.
- Ask them to share live location, not just a static map pin.
- Run `curl -s -X POST http://127.0.0.1:8000/telegram/poll | python -m json.tool`.
- Check `/status` events for `telegram_rejected_sender`, `telegram_location_received`, or `telegram_message_without_media`.

If Twilio is not ready:

- The app can still compute `leave_by` and `call_start_at`, but it cannot call recipients. Use `/status` manually and call/text from your phone.

## What To Watch

Status URL:

```text
http://127.0.0.1:8000/status
```

Fields:

- `last_error`: must be `null`.
- `plan.leave_by`: the time recipients should leave.
- `plan.call_start_at`: when calls start.
- `call_attempts`: should climb only after `call_start_at`.
- `proof_accepted`: once true, calls stop.
- `events`: recent audit trail.
