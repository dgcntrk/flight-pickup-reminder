import asyncio
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from .config import load_settings
from .mock import mock_proof
from .orchestrator import ReminderOrchestrator
from .proof import ProofEvaluator
from .providers.flightaware import FlightStatusProvider
from .providers.google_routes import RouteProvider
from .providers.telegram_gateway import TelegramGateway
from .providers.twilio_gateway import TwilioGateway, public_request_url
from .readiness import readiness_report
from .state import StateStore
from .telegram_intake import TelegramProofIntake


settings = load_settings()
store = StateStore(settings.state_path)
twilio = TwilioGateway(settings)
orchestrator = ReminderOrchestrator(
    settings=settings,
    store=store,
    flights=FlightStatusProvider(settings),
    routes=RouteProvider(settings),
    twilio=twilio,
)
proof_evaluator = ProofEvaluator(settings, twilio)
telegram_gateway = TelegramGateway(settings)
telegram_intake = TelegramProofIntake(telegram_gateway, proof_evaluator, orchestrator, store)
scheduler = AsyncIOScheduler()

app = FastAPI(title="Flight Pickup Reminder", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    config_error = settings.require_live_call_config()
    if config_error:
        store.append_event("config_warning", {"warning": config_error})
    if not scheduler.running:
        scheduler.add_job(orchestrator.tick, "interval", seconds=settings.poll_seconds, id="poll", replace_existing=True)
        scheduler.add_job(
            orchestrator.call_tick,
            "interval",
            seconds=settings.call_interval_seconds,
            id="call_poll",
            replace_existing=True,
        )
        if settings.telegram_polling_enabled and settings.telegram_bot_token:
            scheduler.add_job(
                telegram_intake.poll_once,
                "interval",
                seconds=settings.telegram_poll_seconds,
                id="telegram_poll",
                replace_existing=True,
            )
        scheduler.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/status")
async def status() -> Dict[str, Any]:
    return store.load()


@app.get("/config-check")
async def config_check() -> Dict[str, Any]:
    return readiness_report(settings)


@app.post("/tick")
async def tick() -> Dict[str, Any]:
    return await asyncio.to_thread(orchestrator.tick)


@app.post("/telegram/poll")
async def telegram_poll() -> Dict[str, Any]:
    return await asyncio.to_thread(telegram_intake.poll_once)


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request) -> Dict[str, Any]:
    if settings.telegram_webhook_secret:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if supplied != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid Telegram secret")
    update = await request.json()
    await asyncio.to_thread(telegram_intake.handle_update, update)
    return {"ok": True}


@app.post("/mock/reset")
async def mock_reset() -> Dict[str, Any]:
    _require_mock_enabled()
    state = store.default_state()
    store.save(state)
    store.append_event("mock_reset")
    return store.load()


@app.post("/mock/proof/accept")
async def mock_accept_proof() -> Dict[str, Any]:
    _require_mock_enabled()
    return orchestrator.record_proof(mock_proof(True))


@app.post("/mock/proof/reject")
async def mock_reject_proof() -> Dict[str, Any]:
    _require_mock_enabled()
    return orchestrator.record_proof(mock_proof(False))


@app.post("/mock/tick-at")
async def mock_tick_at(now: str) -> Dict[str, Any]:
    _require_mock_enabled()
    parsed_now = _parse_datetime_query(now)
    return await asyncio.to_thread(orchestrator.tick, parsed_now)


@app.post("/webhooks/twilio/inbound")
async def twilio_inbound(request: Request) -> Response:
    form = await request.form()
    payload = dict(form)
    if not _valid_twilio_signature(request, payload):
        return Response("<Response><Message>Invalid signature.</Message></Response>", status_code=403, media_type="application/xml")

    body = str(payload.get("Body", "")).strip()
    from_number = str(payload.get("From", ""))
    if body.upper() == "STOP":
        store.update(opted_out=True, active=False)
        store.append_event("opt_out", {"from": from_number})
        return _twiml_message("Stopped. You will not receive more calls from this reminder.")

    num_media = int(payload.get("NumMedia", "0") or "0")
    if num_media <= 0:
        store.append_event("message_without_media", {"from": from_number, "body": body})
        return _twiml_message(_proof_reply_instruction())

    media_url = str(payload.get("MediaUrl0", ""))
    content_type = str(payload.get("MediaContentType0", "") or "image/jpeg")
    proof = await asyncio.to_thread(proof_evaluator.evaluate_twilio_media, media_url, content_type)
    state = orchestrator.record_proof(proof)
    if state.get("proof_accepted"):
        return _twiml_message("Photo proof accepted. Calls are stopped.")
    return _twiml_message("Photo received, but proof was not accepted yet. Please send a fresh in-car road photo.")


@app.post("/webhooks/twilio/call-status")
async def twilio_call_status(request: Request) -> Dict[str, Any]:
    form = await request.form()
    payload = dict(form)
    if not _valid_twilio_signature(request, payload):
        return {"ok": False, "error": "invalid signature"}
    store.append_event("twilio_call_status", payload)
    return {"ok": True}


@app.api_route("/twiml/voice", methods=["GET", "POST"])
async def twiml_voice() -> Response:
    message = (
        "Pickup reminder. Current flight and traffic timing says it is time to leave. "
        + _proof_reply_instruction()
    )
    return Response(
        "<Response><Say voice=\"alice\">{}</Say></Response>".format(escape(message)),
        media_type="application/xml",
    )


def _valid_twilio_signature(request: Request, payload: Dict[str, Any]) -> bool:
    if not settings.twilio_validate_signature:
        return True
    if not settings.twilio_auth_token:
        return False
    signature = request.headers.get("X-Twilio-Signature", "")
    url = public_request_url(settings, request.url.path) or str(request.url)
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, payload, signature)


def _require_mock_enabled() -> None:
    if not settings.mock_enabled:
        raise HTTPException(status_code=404, detail="Mock endpoints are disabled")


def _parse_datetime_query(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Use an ISO datetime, for example 2026-05-16T16:15:00Z") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _twiml_message(message: str) -> Response:
    return Response(
        "<Response><Message>{}</Message></Response>".format(escape(message)),
        media_type="application/xml",
    )


def _proof_reply_instruction() -> str:
    if settings.proof_accept_telegram_location:
        return "Please share your live location with the Telegram bot once you are on the road."
    return "Please reply with a fresh photo from the car once you are on the road."


def run() -> None:
    uvicorn.run("flight_pickup_reminder.api:app", host=settings.host, port=settings.port)
