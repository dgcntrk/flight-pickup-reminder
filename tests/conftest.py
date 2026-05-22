from dataclasses import replace

import pytest

from flight_pickup_reminder.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        mock_enabled=True,
        app_timezone="America/Vancouver",
        host="127.0.0.1",
        port=8000,
        public_base_url="",
        flight_provider="manual",
        flightaware_api_key="",
        flight_ident="MOCK-FLAIR-YEG-YXX",
        flight_origin_icao="CYEG",
        flight_destination_icao="CYXX",
        flight_local_date="2026-05-16",
        manual_arrival_iso="2026-05-16T10:00:00-07:00",
        google_maps_api_key="",
        friends_address="123 Pickup St, Example City, BC, Canada",
        airport_address="Example International Airport, Example City, BC, Canada",
        default_drive_minutes=35,
        airport_arrival_buffer_minutes=5,
        call_lead_minutes=5,
        poll_seconds=60,
        call_interval_seconds=30,
        max_call_attempts=12,
        calling_enabled=False,
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_api_key_sid="",
        twilio_api_key_secret="",
        twilio_from_number="",
        recipient_numbers=["+16045550101", "+16045550102"],
        twilio_validate_signature=False,
        telegram_bot_token="",
        telegram_allowed_user_ids=[],
        telegram_allow_any_until="",
        telegram_polling_enabled=False,
        telegram_poll_seconds=5,
        telegram_webhook_secret="",
        openai_api_key="",
        openai_vision_model="gpt-4.1-mini",
        proof_accept_telegram_location=False,
        proof_require_telegram_live_location=True,
        proof_require_telegram_movement=False,
        telegram_location_min_movement_meters=25,
        proof_require_telegram_pickup_area=False,
        telegram_pickup_latitude=None,
        telegram_pickup_longitude=None,
        telegram_pickup_radius_meters=15000,
        telegram_location_max_age_minutes=10,
        telegram_location_max_accuracy_meters=1500,
        proof_mock_mode="off",
        proof_require_iphone_exif=True,
        proof_max_age_minutes=20,
        proof_store_dir=str(tmp_path / "proofs"),
        state_path=str(tmp_path / "state.json"),
    )


@pytest.fixture
def settings_factory(settings):
    def factory(**changes):
        return replace(settings, **changes)

    return factory
