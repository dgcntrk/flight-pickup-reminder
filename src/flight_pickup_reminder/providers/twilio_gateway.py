from datetime import datetime, timezone
from typing import Optional

import requests

from ..config import Settings
from ..models import CallResult


class TwilioGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def place_call(self, to_number: str, message: str) -> CallResult:
        config_error = self.settings.require_live_call_config()
        if config_error or not self.settings.calling_enabled:
            return CallResult(
                to_number=to_number,
                provider="twilio",
                sid=None,
                status="dry_run",
                dry_run=True,
                message=config_error or "CALLING_ENABLED=false",
            )

        twiml = (
            "<Response>"
            "<Say voice=\"alice\">"
            + self._escape_twiml(message)
            + "</Say>"
            "</Response>"
        )
        data = [
            ("To", to_number),
            ("From", self.settings.twilio_from_number),
            ("Twiml", twiml),
            ("StatusCallbackEvent", "initiated"),
            ("StatusCallbackEvent", "ringing"),
            ("StatusCallbackEvent", "answered"),
            ("StatusCallbackEvent", "completed"),
        ]
        callback_url = self._callback_url("/webhooks/twilio/call-status")
        if callback_url:
            data.append(("StatusCallback", callback_url))
            data.append(("StatusCallbackMethod", "POST"))

        url = "https://api.twilio.com/2010-04-01/Accounts/{}/Calls.json".format(
            self.settings.twilio_account_sid
        )
        response = requests.post(
            url,
            data=data,
            auth=self.settings.twilio_rest_auth,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return CallResult(
            to_number=to_number,
            provider="twilio",
            sid=payload.get("sid"),
            status=payload.get("status", "queued"),
            dry_run=False,
            message="call requested at " + datetime.now(timezone.utc).isoformat(),
        )

    def download_media(self, media_url: str) -> requests.Response:
        auth: Optional[tuple] = self.settings.twilio_rest_auth
        response = requests.get(media_url, auth=auth, timeout=30)
        response.raise_for_status()
        return response

    def _callback_url(self, path: str) -> Optional[str]:
        if not self.settings.public_base_url:
            return None
        return self.settings.public_base_url + path

    @staticmethod
    def _escape_twiml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


def public_request_url(settings: Settings, path: str) -> Optional[str]:
    if not settings.public_base_url:
        return None
    return settings.public_base_url + path
