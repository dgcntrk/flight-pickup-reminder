import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _optional_float(name: str) -> Optional[float]:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return float(value)


def _csv(name: str) -> List[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _csv_int(name: str) -> List[int]:
    values = []
    for item in _csv(name):
        try:
            values.append(int(item))
        except ValueError:
            continue
    return values


@dataclass(frozen=True)
class Settings:
    mock_enabled: bool
    app_timezone: str
    host: str
    port: int
    public_base_url: str
    flight_provider: str
    flightaware_api_key: str
    flight_ident: str
    flight_origin_icao: str
    flight_destination_icao: str
    flight_local_date: str
    manual_arrival_iso: str
    google_maps_api_key: str
    friends_address: str
    airport_address: str
    default_drive_minutes: int
    airport_arrival_buffer_minutes: int
    call_lead_minutes: int
    poll_seconds: int
    call_interval_seconds: int
    max_call_attempts: int
    calling_enabled: bool
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_api_key_sid: str
    twilio_api_key_secret: str
    twilio_from_number: str
    recipient_numbers: List[str]
    twilio_validate_signature: bool
    telegram_bot_token: str
    telegram_allowed_user_ids: List[int]
    telegram_allow_any_until: str
    telegram_polling_enabled: bool
    telegram_poll_seconds: int
    telegram_webhook_secret: str
    openai_api_key: str
    openai_vision_model: str
    proof_accept_telegram_location: bool
    proof_require_telegram_live_location: bool
    proof_require_telegram_movement: bool
    telegram_location_min_movement_meters: int
    proof_require_telegram_pickup_area: bool
    telegram_pickup_latitude: Optional[float]
    telegram_pickup_longitude: Optional[float]
    telegram_pickup_radius_meters: int
    telegram_location_max_age_minutes: int
    telegram_location_max_accuracy_meters: int
    proof_mock_mode: str
    proof_require_iphone_exif: bool
    proof_max_age_minutes: int
    proof_store_dir: str
    state_path: str

    @property
    def callbacks_enabled(self) -> bool:
        return bool(self.public_base_url)

    @property
    def twilio_rest_auth(self) -> Optional[tuple]:
        if self.twilio_api_key_sid and self.twilio_api_key_secret:
            return (self.twilio_api_key_sid, self.twilio_api_key_secret)
        if self.twilio_account_sid and self.twilio_auth_token:
            return (self.twilio_account_sid, self.twilio_auth_token)
        return None

    def require_live_call_config(self) -> Optional[str]:
        if not self.calling_enabled:
            return None
        missing = []
        if not self.twilio_account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.twilio_rest_auth:
            missing.append("TWILIO_AUTH_TOKEN or TWILIO_API_KEY_SID/TWILIO_API_KEY_SECRET")
        if not self.twilio_from_number:
            missing.append("TWILIO_FROM_NUMBER")
        if not self.recipient_numbers:
            missing.append("RECIPIENT_NUMBERS")
        if missing:
            return "Calling is enabled but missing: " + ", ".join(missing)
        return None


def load_settings() -> Settings:
    load_dotenv(os.getenv("ENV_FILE", ".env"))
    return Settings(
        mock_enabled=_bool("MOCK_ENABLED", False),
        app_timezone=os.getenv("APP_TIMEZONE", "America/Vancouver"),
        host=os.getenv("HOST", "127.0.0.1"),
        port=_int("PORT", 8000),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
        flight_provider=os.getenv("FLIGHT_PROVIDER", "flightaware"),
        flightaware_api_key=os.getenv("FLIGHTAWARE_API_KEY", ""),
        flight_ident=os.getenv("FLIGHT_IDENT", ""),
        flight_origin_icao=os.getenv("FLIGHT_ORIGIN_ICAO", ""),
        flight_destination_icao=os.getenv("FLIGHT_DESTINATION_ICAO", ""),
        flight_local_date=os.getenv("FLIGHT_LOCAL_DATE", ""),
        manual_arrival_iso=os.getenv("MANUAL_ARRIVAL_ISO", ""),
        google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        friends_address=os.getenv("FRIENDS_ADDRESS", ""),
        airport_address=os.getenv("AIRPORT_ADDRESS", ""),
        default_drive_minutes=_int("DEFAULT_DRIVE_MINUTES", 35),
        airport_arrival_buffer_minutes=_int("AIRPORT_ARRIVAL_BUFFER_MINUTES", 5),
        call_lead_minutes=_int("CALL_LEAD_MINUTES", 5),
        poll_seconds=_int("POLL_SECONDS", 60),
        call_interval_seconds=_int("CALL_INTERVAL_SECONDS", 30),
        max_call_attempts=_int("MAX_CALL_ATTEMPTS", 12),
        calling_enabled=_bool("CALLING_ENABLED", False),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_api_key_sid=os.getenv("TWILIO_API_KEY_SID", ""),
        twilio_api_key_secret=os.getenv("TWILIO_API_KEY_SECRET", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
        recipient_numbers=_csv("RECIPIENT_NUMBERS"),
        twilio_validate_signature=_bool("TWILIO_VALIDATE_SIGNATURE", True),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_allowed_user_ids=_csv_int("TELEGRAM_ALLOWED_USER_IDS"),
        telegram_allow_any_until=os.getenv("TELEGRAM_ALLOW_ANY_UNTIL", ""),
        telegram_polling_enabled=_bool("TELEGRAM_POLLING_ENABLED", False),
        telegram_poll_seconds=_int("TELEGRAM_POLL_SECONDS", 5),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini"),
        proof_accept_telegram_location=_bool("PROOF_ACCEPT_TELEGRAM_LOCATION", False),
        proof_require_telegram_live_location=_bool("PROOF_REQUIRE_TELEGRAM_LIVE_LOCATION", True),
        proof_require_telegram_movement=_bool("PROOF_REQUIRE_TELEGRAM_MOVEMENT", False),
        telegram_location_min_movement_meters=_int("TELEGRAM_LOCATION_MIN_MOVEMENT_METERS", 25),
        proof_require_telegram_pickup_area=_bool("PROOF_REQUIRE_TELEGRAM_PICKUP_AREA", False),
        telegram_pickup_latitude=_optional_float("TELEGRAM_PICKUP_LATITUDE"),
        telegram_pickup_longitude=_optional_float("TELEGRAM_PICKUP_LONGITUDE"),
        telegram_pickup_radius_meters=_int("TELEGRAM_PICKUP_RADIUS_METERS", 15000),
        telegram_location_max_age_minutes=_int("TELEGRAM_LOCATION_MAX_AGE_MINUTES", 10),
        telegram_location_max_accuracy_meters=_int("TELEGRAM_LOCATION_MAX_ACCURACY_METERS", 1500),
        proof_mock_mode=os.getenv("PROOF_MOCK_MODE", "off").strip().lower(),
        proof_require_iphone_exif=_bool("PROOF_REQUIRE_IPHONE_EXIF", True),
        proof_max_age_minutes=_int("PROOF_MAX_AGE_MINUTES", 20),
        proof_store_dir=os.getenv("PROOF_STORE_DIR", "data/proofs"),
        state_path=os.getenv("STATE_PATH", "data/state.json"),
    )
