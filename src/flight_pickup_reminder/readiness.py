from typing import Dict, List

from .config import Settings


def readiness_report(settings: Settings) -> Dict[str, object]:
    missing: List[str] = []
    warnings: List[str] = []

    if not settings.flight_ident:
        missing.append("FLIGHT_IDENT")
    if not settings.manual_arrival_iso and not settings.flightaware_api_key:
        missing.append("FLIGHTAWARE_API_KEY")
    if not settings.google_maps_api_key:
        missing.append("GOOGLE_MAPS_API_KEY")
    if not settings.friends_address:
        missing.append("FRIENDS_ADDRESS")
    if not settings.airport_address:
        missing.append("AIRPORT_ADDRESS")

    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_rest_auth:
        missing.append("TWILIO_AUTH_TOKEN or TWILIO_API_KEY_SID/TWILIO_API_KEY_SECRET")
    if not settings.twilio_from_number:
        missing.append("TWILIO_FROM_NUMBER")
    if not settings.recipient_numbers:
        missing.append("RECIPIENT_NUMBERS")
    if not settings.public_base_url:
        missing.append("PUBLIC_BASE_URL")
    if not settings.calling_enabled:
        warnings.append("CALLING_ENABLED is false; calls will be dry-run only")
    if settings.twilio_validate_signature and not settings.twilio_auth_token:
        warnings.append("TWILIO_VALIDATE_SIGNATURE is true but TWILIO_AUTH_TOKEN is missing; Twilio webhooks will be rejected")

    if (
        settings.proof_mock_mode == "off"
        and not settings.proof_accept_telegram_location
        and not settings.openai_api_key
    ):
        missing.append("OPENAI_API_KEY or PROOF_ACCEPT_TELEGRAM_LOCATION=true")
    if settings.proof_accept_telegram_location and not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_bot_token:
        warnings.append("TELEGRAM_BOT_TOKEN is missing; Telegram proof intake is disabled")
    if settings.telegram_allow_any_until:
        warnings.append("Telegram accepts any sender until {}".format(settings.telegram_allow_any_until))
    if settings.telegram_bot_token and not settings.telegram_allowed_user_ids:
        warnings.append("TELEGRAM_ALLOWED_USER_IDS is empty; any Telegram sender can submit proof")
    if settings.telegram_bot_token and not settings.telegram_polling_enabled:
        warnings.append("TELEGRAM_POLLING_ENABLED is false; Telegram proof requires webhook or manual /telegram/poll")
    if settings.proof_mock_mode != "off":
        warnings.append("PROOF_MOCK_MODE is {}; real vision proof is bypassed".format(settings.proof_mock_mode))
    if not settings.proof_require_iphone_exif:
        warnings.append("PROOF_REQUIRE_IPHONE_EXIF is false; EXIF is not required for acceptance")
    if settings.proof_accept_telegram_location:
        warnings.append("Telegram live location proof is enabled; use only with explicit consent")
    if settings.proof_require_telegram_pickup_area:
        if settings.telegram_pickup_latitude is None or settings.telegram_pickup_longitude is None:
            missing.append("TELEGRAM_PICKUP_LATITUDE/TELEGRAM_PICKUP_LONGITUDE")
        else:
            warnings.append("Telegram proof must be within the configured pickup-area geofence")

    return {
        "mock_enabled": settings.mock_enabled,
        "proof_accept_telegram_location": settings.proof_accept_telegram_location,
        "ready_for_live": not missing and settings.calling_enabled and settings.proof_mock_mode == "off",
        "missing": missing,
        "warnings": warnings,
    }
