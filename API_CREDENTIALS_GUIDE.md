# API Credentials Guide

This guide walks through the credentials needed to run Flight Pickup Reminder with real APIs. Replace every placeholder before enabling live calls.

## Minimum Live Checklist

Required accounts or services:

1. Twilio account with a Voice + SMS/MMS capable phone number.
2. Telegram bot token for live-location proof intake.
3. Public HTTPS tunnel or deployment URL for optional webhooks and status access.
4. Google Maps Platform API key with Routes API enabled.
5. FlightAware AeroAPI key, unless you use `MANUAL_ARRIVAL_ISO` as the fallback.
6. Optional OpenAI API key only if you want photo proof fallback.

Required non-API details:

1. Exact flight number from the booking or airline status page.
2. Exact pickup address.
3. Recipient numbers in E.164 format, for example `+16045550101,+16045550102`.
4. Explicit consent from recipients for repeated calls/texts and live-location proof.

## Priority Order For The Morning

Do these first because they are the most likely to block live use:

1. Twilio: create/upgrade account, get a phone number, verify recipient numbers if still on trial.
2. Telegram: confirm bot works and collect allowed user IDs.
3. Telegram live-location proof: avoids needing an OpenAI key for the main proof flow.
4. Google Routes key: needed for live traffic drive time.
5. FlightAware key: ideal, but if setup takes too long, use `MANUAL_ARRIVAL_ISO` from the airline or airport status page.

## Twilio

Needed environment variables:

```env
CALLING_ENABLED=true
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_API_KEY_SID=
TWILIO_API_KEY_SECRET=
TWILIO_FROM_NUMBER=+1...
RECIPIENT_NUMBERS=+1604...,+1604...
PUBLIC_BASE_URL=https://YOUR_PUBLIC_URL
TWILIO_VALIDATE_SIGNATURE=true
```

`TWILIO_AUTH_TOKEN` can be replaced for outbound REST calls by a Twilio API key:

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_API_KEY_SID=SK...
TWILIO_API_KEY_SECRET=...
```

Keep `TWILIO_AUTH_TOKEN` if `TWILIO_VALIDATE_SIGNATURE=true`; Twilio webhook signature validation uses the account Auth Token, not the API key secret.

When verifying a Standard API key, test an account-scoped product endpoint such as:

```text
GET /2010-04-01/Accounts/{AccountSid}/IncomingPhoneNumbers.json
GET /2010-04-01/Accounts/{AccountSid}/Calls.json
```

Do not use `GET /2010-04-01/Accounts/{AccountSid}.json` as the API-key verification test. Twilio Standard API keys cannot access Account resources, so that endpoint can return an authentication failure even when the key is valid for calls and phone-number resources.

Steps:

1. Go to https://www.twilio.com/console and sign in or create an account.
2. If the account is a trial, verify both friend numbers under verified recipients/caller IDs. Trial accounts can only message/call verified phone numbers.
3. Upgrade the account if possible. This removes verified-recipient restrictions and enables custom message/call behavior more reliably.
4. Go to **Products & Services > Numbers & Senders > Phone Numbers**.
5. Set up or buy a number with **Voice**, **SMS**, and **MMS** support. A Canadian number may require compliance registration; if time is tight, use any number Twilio lets you activate quickly that can call/message Canadian mobile numbers.
6. Copy the Account SID and Auth Token from the Twilio Console, or copy the Account SID plus an API Key SID and secret.
7. Put the Twilio number into `TWILIO_FROM_NUMBER`.
8. Configure the Twilio number's Messaging webhook:

```text
Webhook URL: https://YOUR_PUBLIC_URL/webhooks/twilio/inbound
Method: POST
```

The app supplies call instructions inline when it creates outbound calls, so you do not need to configure an inbound voice webhook for this project. Call status callbacks are attached by the app when `PUBLIC_BASE_URL` is set.

Relevant docs:

- Phone numbers: https://www.twilio.com/docs/numbers-and-senders/phone-number-senders
- Trial restrictions: https://www.twilio.com/docs/usage/trials
- Outbound Call resource: https://www.twilio.com/docs/voice/api/call-resource
- Messaging webhook media fields: https://www.twilio.com/docs/messaging/guides/webhook-request

## Public HTTPS URL

Needed environment variable:

```env
PUBLIC_BASE_URL=https://YOUR_PUBLIC_URL
```

Fast path with ngrok:

```sh
ngrok http 8000
```

Copy the HTTPS forwarding URL, for example:

```text
https://abc123.ngrok-free.app
```

Set:

```env
PUBLIC_BASE_URL=https://abc123.ngrok-free.app
```

Then update Twilio's Messaging webhook to:

```text
https://abc123.ngrok-free.app/webhooks/twilio/inbound
```

If ngrok restarts and gives a new URL, update both `.env` and the Twilio webhook.

Relevant docs:

- ngrok local webhook testing: https://ngrok.com/docs/guides/share-localhost/webhooks

## Telegram Bot

Needed environment variables:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
TELEGRAM_POLLING_ENABLED=true
TELEGRAM_POLL_SECONDS=5
PROOF_ACCEPT_TELEGRAM_LOCATION=true
PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=true
TELEGRAM_LOCATION_MAX_AGE_MINUTES=10
TELEGRAM_LOCATION_MAX_ACCURACY_METERS=1500
```

Steps:

1. Open Telegram.
2. Ask each friend to message the bot once. `/start` is enough for ID discovery.
3. Poll once:

```sh
curl -s -X POST http://127.0.0.1:8000/telegram/poll | python -m json.tool
```

4. Check recent events:

```sh
curl -s http://127.0.0.1:8000/status | python -m json.tool | grep sender_id
```

5. Copy those numeric IDs into:

```env
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

6. Restart the app.

For proof, ask them to open the bot chat, tap the attachment icon, choose **Location**, and use **Share Live Location** for long enough to cover the pickup window. The app accepts active, fresh live location by default and rejects static map pins unless `PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=false`.

Relevant docs:

- Telegram Bot API: https://core.telegram.org/bots/api
- `getUpdates`: https://core.telegram.org/bots/api#getupdates
- `Location`: https://core.telegram.org/bots/api#location
- Live locations: https://core.telegram.org/bots/api#sendlocation

## Optional OpenAI Photo Fallback

Needed environment variables:

```env
OPENAI_API_KEY=sk-...
OPENAI_VISION_MODEL=gpt-4.1-mini
PROOF_MOCK_MODE=off
PROOF_REQUIRE_IPHONE_EXIF=true
```

Steps:

1. Go to https://platform.openai.com/settings/organization/api-keys.
2. Create a new secret key.
3. Put it in `.env` as `OPENAI_API_KEY`.
4. Keep `PROOF_MOCK_MODE=off` for live use.
5. Keep `PROOF_REQUIRE_IPHONE_EXIF=true` if you want strict metadata checking.

Important: this is no longer required when `PROOF_ACCEPT_TELEGRAM_LOCATION=true`. iMessage/MMS can strip EXIF. If real iPhone photos are rejected because EXIF is missing, set `PROOF_REQUIRE_IPHONE_EXIF=false` and rely on the OpenAI vision check, or prefer Telegram live location.

### What about using your Codex subscription for photo proof?

Codex CLI can run non-interactively and attach images with `codex exec --image`, and Codex can be signed in with ChatGPT subscription access. That makes it fine for local, trusted, one-off image checks. It is not the recommended unattended proof backend for this service: official Codex docs recommend API-key auth for programmatic workflows, and a long-running Telegram intake would have to shell out to a local Codex session and parse agent output. The no-OpenAI-key path in this repo is Telegram live location. Keep `OPENAI_API_KEY` only if you deliberately want the optional photo fallback.

Relevant docs:

- Codex authentication: https://developers.openai.com/codex/auth
- Codex non-interactive mode: https://developers.openai.com/codex/noninteractive
- Image inputs / vision: https://developers.openai.com/api/docs/guides/images-vision
- Structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs

## Google Maps Platform Routes API

Needed environment variables:

```env
GOOGLE_MAPS_API_KEY=AIza...
FRIENDS_ADDRESS=EXACT PICKUP ADDRESS
AIRPORT_ADDRESS=EXACT AIRPORT ADDRESS
```

Steps:

1. Go to https://console.cloud.google.com/google/maps-apis.
2. Create or select a Google Cloud project.
3. Enable billing for the project.
4. Enable **Routes API**.
5. Create an API key under **APIs & Services > Credentials**.
6. Restrict the key to **Routes API**. If you know the server's IP address, add an IP restriction; for local ngrok testing, API restriction alone may be the practical temporary option.
7. Put the key into `GOOGLE_MAPS_API_KEY`.
8. Replace `FRIENDS_ADDRESS` with the exact pickup address.

Quick test:

```sh
curl -s -X POST 'https://routes.googleapis.com/directions/v2:computeRoutes' \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $GOOGLE_MAPS_API_KEY" \
  -H "X-Goog-FieldMask: routes.duration,routes.staticDuration,routes.distanceMeters" \
  -d '{
    "origin": {"address": "YOUR EXACT PICKUP ADDRESS"},
    "destination": {"address": "YOUR EXACT AIRPORT ADDRESS"},
    "travelMode": "DRIVE",
    "routingPreference": "TRAFFIC_AWARE_OPTIMAL"
  }'
```

Relevant docs:

- Routes API billing/API key requirement: https://developers.google.com/maps/documentation/routes/usage-and-billing
- `computeRoutes`: https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
- Traffic-aware routing: https://developers.google.com/maps/documentation/routes/config_trade_offs
- API key security: https://developers.google.com/maps/api-security-best-practices

## FlightAware AeroAPI

Needed environment variables:

```env
FLIGHT_PROVIDER=flightaware
FLIGHTAWARE_API_KEY=...
FLIGHT_IDENT=F8...
FLIGHT_ORIGIN_ICAO=ORIGIN_ICAO
FLIGHT_DESTINATION_ICAO=DESTINATION_ICAO
FLIGHT_LOCAL_DATE=YYYY-MM-DD
MANUAL_ARRIVAL_ISO=
```

Steps:

1. Go to https://www.flightaware.com/commercial/aeroapi.
2. Sign in or create a FlightAware account.
3. Activate an AeroAPI plan or trial if available.
4. Open the AeroAPI portal and copy the API key.
5. Put it into `FLIGHTAWARE_API_KEY`.
6. Put the exact airline flight number into `FLIGHT_IDENT`.
7. Set `FLIGHT_LOCAL_DATE` to the local date of the flight.

Quick test:

```sh
curl -s "https://aeroapi.flightaware.com/aeroapi/flights/$FLIGHT_IDENT?max_pages=1" \
  -H "Accept: application/json" \
  -H "x-apikey: $FLIGHTAWARE_API_KEY" \
  | python -m json.tool | sed -n '1,80p'
```

Fallback if FlightAware setup is slow:

```env
MANUAL_ARRIVAL_ISO=2026-05-16T10:00:00-07:00
```

Use the actual arrival estimate from the airline or airport status page and update that value manually.

Relevant docs:

- AeroAPI product: https://www.flightaware.com/commercial/aeroapi
- AeroAPI key/header examples: https://support.flightaware.com/hc/en-us/articles/33154420450071-Why-Is-My-AeroAPI-Key-Returning-Invalid
