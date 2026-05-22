from flight_pickup_reminder.providers.twilio_gateway import TwilioGateway


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"sid": "CA123", "status": "queued"}


def test_twilio_gateway_uses_api_key_credentials_for_rest_calls(settings_factory, monkeypatch):
    settings = settings_factory(
        calling_enabled=True,
        twilio_account_sid="AC123",
        twilio_auth_token="",
        twilio_api_key_sid="SK123",
        twilio_api_key_secret="api-secret",
        twilio_from_number="+16045550100",
        recipient_numbers=["+16045550101"],
    )
    calls = []

    def fake_post(url, data, auth, timeout):
        calls.append({"url": url, "auth": auth, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("flight_pickup_reminder.providers.twilio_gateway.requests.post", fake_post)

    result = TwilioGateway(settings).place_call("+16045550101", "Leave now.")

    assert result.sid == "CA123"
    assert calls[0]["url"].endswith("/Accounts/AC123/Calls.json")
    assert calls[0]["auth"] == ("SK123", "api-secret")


def test_twilio_gateway_falls_back_to_auth_token_for_rest_calls(settings_factory, monkeypatch):
    settings = settings_factory(
        calling_enabled=True,
        twilio_account_sid="AC123",
        twilio_auth_token="auth-token",
        twilio_api_key_sid="",
        twilio_api_key_secret="",
        twilio_from_number="+16045550100",
        recipient_numbers=["+16045550101"],
    )
    calls = []

    def fake_post(url, data, auth, timeout):
        calls.append({"auth": auth})
        return FakeResponse()

    monkeypatch.setattr("flight_pickup_reminder.providers.twilio_gateway.requests.post", fake_post)

    TwilioGateway(settings).place_call("+16045550101", "Leave now.")

    assert calls[0]["auth"] == ("AC123", "auth-token")
