from flight_pickup_reminder.readiness import readiness_report


def test_readiness_reports_mock_mode_warnings(settings_factory):
    settings = settings_factory(
        manual_arrival_iso="2026-05-16T10:00:00-07:00",
        flightaware_api_key="",
        google_maps_api_key="",
        proof_mock_mode="accept",
        proof_require_iphone_exif=False,
    )

    report = readiness_report(settings)

    assert "GOOGLE_MAPS_API_KEY" in report["missing"]
    assert report["ready_for_live"] is False
    assert any("PROOF_MOCK_MODE" in warning for warning in report["warnings"])


def test_readiness_passes_when_live_config_is_present(settings_factory):
    settings = settings_factory(
        mock_enabled=False,
        manual_arrival_iso="",
        flightaware_api_key="fa-key",
        google_maps_api_key="google-key",
        twilio_account_sid="AC123",
        twilio_auth_token="twilio-token",
        twilio_from_number="+16045550100",
        public_base_url="https://example.ngrok-free.app",
        openai_api_key="sk-test",
        telegram_bot_token="telegram-token",
        telegram_allowed_user_ids=[1234],
        telegram_allow_any_until="",
        telegram_polling_enabled=True,
        calling_enabled=True,
        proof_mock_mode="off",
        proof_require_iphone_exif=True,
        friends_address="123 Pickup St, Example City, BC, Canada",
    )

    report = readiness_report(settings)

    assert report["missing"] == []
    assert report["ready_for_live"] is True


def test_readiness_accepts_twilio_api_key_for_rest_auth(settings_factory):
    settings = settings_factory(
        mock_enabled=False,
        manual_arrival_iso="",
        flightaware_api_key="fa-key",
        google_maps_api_key="google-key",
        twilio_account_sid="AC123",
        twilio_auth_token="",
        twilio_api_key_sid="SK123",
        twilio_api_key_secret="twilio-api-key-secret",
        twilio_from_number="+16045550100",
        public_base_url="https://example.ngrok-free.app",
        openai_api_key="sk-test",
        telegram_bot_token="telegram-token",
        telegram_allowed_user_ids=[1234],
        telegram_allow_any_until="",
        telegram_polling_enabled=True,
        twilio_validate_signature=False,
        calling_enabled=True,
        proof_mock_mode="off",
        proof_require_iphone_exif=True,
        friends_address="123 Pickup St, Example City, BC, Canada",
    )

    report = readiness_report(settings)

    assert report["missing"] == []
    assert report["ready_for_live"] is True


def test_readiness_allows_telegram_location_instead_of_openai_key(settings_factory):
    settings = settings_factory(
        mock_enabled=False,
        manual_arrival_iso="",
        flightaware_api_key="fa-key",
        google_maps_api_key="google-key",
        twilio_account_sid="AC123",
        twilio_auth_token="twilio-token",
        twilio_from_number="+16045550100",
        public_base_url="https://example.ngrok-free.app",
        openai_api_key="",
        telegram_bot_token="telegram-token",
        telegram_allowed_user_ids=[1234],
        telegram_allow_any_until="",
        telegram_polling_enabled=True,
        calling_enabled=True,
        proof_mock_mode="off",
        proof_accept_telegram_location=True,
        proof_require_iphone_exif=True,
        friends_address="123 Pickup St, Example City, BC, Canada",
    )

    report = readiness_report(settings)

    assert report["missing"] == []
    assert report["ready_for_live"] is True
