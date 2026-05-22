from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import Settings, load_settings
from .mock import mock_proof
from .orchestrator import ReminderOrchestrator
from .planning import PlanningConfig, build_reminder_plan
from .providers.flightaware import FlightStatusProvider
from .providers.google_routes import RouteProvider
from .providers.twilio_gateway import TwilioGateway
from .readiness import readiness_report
from .state import StateStore
from .time_utils import parse_iso_datetime


PRIVATE_KEYS = {
    "from",
    "last_call_to",
    "latitude",
    "longitude",
    "media_path",
    "phone_number",
    "recipient_numbers",
    "sender_id",
    "telegram_location_tracks",
    "to",
}


ENV_TEMPLATE = """APP_TIMEZONE=America/Vancouver
HOST=127.0.0.1
PORT=8000
PUBLIC_BASE_URL=
MOCK_ENABLED=false

FLIGHT_PROVIDER=flightaware
FLIGHTAWARE_API_KEY=
FLIGHT_IDENT=
FLIGHT_ORIGIN_ICAO=
FLIGHT_DESTINATION_ICAO=
FLIGHT_LOCAL_DATE=YYYY-MM-DD
MANUAL_ARRIVAL_ISO=

GOOGLE_MAPS_API_KEY=
FRIENDS_ADDRESS=YOUR EXACT PICKUP ADDRESS
AIRPORT_ADDRESS=YOUR EXACT AIRPORT ADDRESS
DEFAULT_DRIVE_MINUTES=35

AIRPORT_ARRIVAL_BUFFER_MINUTES=5
CALL_LEAD_MINUTES=5
POLL_SECONDS=60
CALL_INTERVAL_SECONDS=30
MAX_CALL_ATTEMPTS=12

CALLING_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_API_KEY_SID=
TWILIO_API_KEY_SECRET=
TWILIO_FROM_NUMBER=
RECIPIENT_NUMBERS=
TWILIO_VALIDATE_SIGNATURE=true

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
TELEGRAM_ALLOW_ANY_UNTIL=
TELEGRAM_POLLING_ENABLED=true
TELEGRAM_POLL_SECONDS=5
TELEGRAM_WEBHOOK_SECRET=

PROOF_ACCEPT_TELEGRAM_LOCATION=true
PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION=true
PROOF_REQUIRE_TELEGRAM_MOVEMENT=false
TELEGRAM_LOCATION_MIN_MOVEMENT_METERS=25
PROOF_REQUIRE_TELEGRAM_PICKUP_AREA=false
TELEGRAM_PICKUP_LATITUDE=
TELEGRAM_PICKUP_LONGITUDE=
TELEGRAM_PICKUP_RADIUS_METERS=15000
TELEGRAM_LOCATION_MAX_AGE_MINUTES=10
TELEGRAM_LOCATION_MAX_ACCURACY_METERS=1500

OPENAI_API_KEY=
OPENAI_VISION_MODEL=gpt-4.1-mini
PROOF_MOCK_MODE=off
PROOF_REQUIRE_IPHONE_EXIF=true
PROOF_MAX_AGE_MINUTES=20
PROOF_STORE_DIR=data/proofs
STATE_PATH=data/state.json
"""


def get_status(include_private: bool = False, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Return current reminder state, redacted by default for agent context."""
    loaded_settings = settings or load_settings()
    state = StateStore(loaded_settings.state_path).load()
    return _jsonable(state if include_private else _redact(state))


def check_readiness(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Return live-readiness checks without exposing credential values."""
    return _jsonable(readiness_report(settings or load_settings()))


def get_setup_guide(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Return setup guidance an agent can use to onboard a first-time user."""
    loaded_settings = settings or load_settings()
    report = readiness_report(loaded_settings)
    return {
        "summary": (
            "Flight Pickup Reminder needs flight timing, route timing, recipient consent, "
            "Twilio calling credentials, and Telegram live-location proof before live use."
        ),
        "safe_default": "CALLING_ENABLED=false keeps all calls in dry-run mode until the user explicitly enables live calls.",
        "one_liner_after_pypi_publish": (
            "claude mcp add --transport stdio flight-pickup-reminder -- "
            "uvx flight-pickup-reminder-mcp"
        ),
        "one_liner_from_github": (
            "claude mcp add --transport stdio flight-pickup-reminder -- "
            "uvx --from git+https://github.com/dgcntrk/flight-pickup-reminder flight-pickup-reminder-mcp"
        ),
        "first_agent_prompt": (
            "Use the flight-pickup-reminder MCP server to show me the setup checklist, "
            "check readiness, and preview the pickup plan. Do not place live calls unless I explicitly confirm."
        ),
        "minimum_live_accounts": [
            "Twilio account and phone number for calls/SMS",
            "Telegram bot token and allowed Telegram sender IDs for live-location proof",
            "Google Maps Platform key with Routes API enabled",
            "FlightAware AeroAPI key, or MANUAL_ARRIVAL_ISO as a fallback",
            "Optional OpenAI API key only for photo proof fallback",
        ],
        "minimum_user_inputs": [
            "Exact flight identifier and local flight date",
            "Exact pickup address and airport address",
            "Recipient phone numbers in E.164 format",
            "Explicit consent from every recipient",
        ],
        "recommended_order": [
            "Create a local .env from the template returned by this tool",
            "Keep CALLING_ENABLED=false",
            "Run check_pickup_readiness",
            "Configure Telegram and collect TELEGRAM_ALLOWED_USER_IDS",
            "Configure Google Routes and either FlightAware or MANUAL_ARRIVAL_ISO",
            "Run preview_pickup_plan and inspect leave_by/call_start_at",
            "Enable CALLING_ENABLED=true only after a successful dry run and explicit consent",
        ],
        "dotenv_template": ENV_TEMPLATE,
        "readiness": report,
    }


def preview_reminder_plan(
    save_to_state: bool = True,
    include_private: bool = False,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Fetch flight/route snapshots and compute a leave-by plan without placing calls."""
    loaded_settings = settings or load_settings()
    store = StateStore(loaded_settings.state_path)
    try:
        flight = FlightStatusProvider(loaded_settings).get_snapshot()
        route = RouteProvider(loaded_settings).get_snapshot()
        plan = build_reminder_plan(
            flight,
            route,
            PlanningConfig(
                airport_arrival_buffer_minutes=loaded_settings.airport_arrival_buffer_minutes,
                call_lead_minutes=loaded_settings.call_lead_minutes,
            ),
        )
        result: Dict[str, Any] = {
            "ok": True,
            "flight": flight,
            "route": route,
            "plan": plan,
        }
        if save_to_state:
            state = store.load()
            state.update({"flight": flight, "route": route, "plan": plan, "last_error": None})
            store.save(state)
            store.append_event("mcp_plan_preview")
        return _jsonable(result if include_private else _redact(result))
    except Exception as exc:
        if save_to_state:
            store.update(last_error=str(exc))
            store.append_event("mcp_plan_preview_error", {"error": str(exc)})
        return {"ok": False, "error": str(exc)}


def run_reminder_tick(
    now_iso: Optional[str] = None,
    allow_live_calls: bool = False,
    include_private: bool = False,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Run one orchestrator tick.

    By default this forces Twilio into dry-run mode even if the local env enables
    live calling. Set allow_live_calls=True only after explicit user approval.
    """
    loaded_settings = settings or load_settings()
    runtime_settings = loaded_settings if allow_live_calls else replace(loaded_settings, calling_enabled=False)
    now = _parse_optional_datetime(now_iso)
    orchestrator = _orchestrator(runtime_settings)
    state = orchestrator.tick(now)
    return _jsonable(state if include_private else _redact(state))


def reset_mock_state(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Reset state when MOCK_ENABLED=true."""
    loaded_settings = settings or load_settings()
    _require_mock_enabled(loaded_settings)
    store = StateStore(loaded_settings.state_path)
    store.save(store.default_state())
    store.append_event("mcp_mock_reset")
    return _jsonable(store.load())


def record_mock_proof(accepted: bool = True, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Record accepted or rejected mock proof when MOCK_ENABLED=true."""
    loaded_settings = settings or load_settings()
    _require_mock_enabled(loaded_settings)
    orchestrator = _orchestrator(loaded_settings)
    return _jsonable(orchestrator.record_proof(mock_proof(accepted, "MCP mock proof")))


def _orchestrator(settings: Settings) -> ReminderOrchestrator:
    store = StateStore(settings.state_path)
    return ReminderOrchestrator(
        settings=settings,
        store=store,
        flights=FlightStatusProvider(settings),
        routes=RouteProvider(settings),
        twilio=TwilioGateway(settings),
    )


def _require_mock_enabled(settings: Settings) -> None:
    if not settings.mock_enabled:
        raise ValueError("MOCK_ENABLED must be true for this MCP tool")


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_iso_datetime(value)
    if parsed is None:
        raise ValueError("Use an ISO datetime, for example 2026-05-16T16:15:00Z")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _redact(value: Any) -> Any:
    if is_dataclass(value):
        return _redact(asdict(value))
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if text_key in PRIVATE_KEYS:
                redacted[text_key] = "[redacted]"
            else:
                redacted[text_key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
