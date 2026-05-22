from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from ..config import Settings
from ..models import RouteSnapshot


def _parse_duration_seconds(value: Optional[str]) -> Optional[int]:
    if not value or not value.endswith("s"):
        return None
    number = value[:-1]
    try:
        return int(float(number))
    except ValueError:
        return None


class RouteProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_snapshot(self) -> RouteSnapshot:
        if not self.settings.google_maps_api_key:
            return self._fallback_snapshot()
        return self._google_routes_snapshot()

    def _fallback_snapshot(self) -> RouteSnapshot:
        return RouteSnapshot(
            provider="manual",
            duration_seconds=self.settings.default_drive_minutes * 60,
            static_duration_seconds=None,
            distance_meters=None,
            updated_at=datetime.now(timezone.utc),
            raw={"default_drive_minutes": self.settings.default_drive_minutes},
        )

    def _google_routes_snapshot(self) -> RouteSnapshot:
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        body = {
            "origin": {"address": self.settings.friends_address},
            "destination": {"address": self.settings.airport_address},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "departureTime": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat().replace("+00:00", "Z"),
            "languageCode": "en-CA",
            "units": "METRIC",
        }
        response = requests.post(
            url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.settings.google_maps_api_key,
                "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters,routes.localizedValues",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes") or []
        if not routes:
            raise RuntimeError("Google Routes returned no routes")
        route = routes[0]
        duration_seconds = _parse_duration_seconds(route.get("duration"))
        if duration_seconds is None:
            raise RuntimeError("Google Routes returned no route duration")
        return RouteSnapshot(
            provider="google_routes",
            duration_seconds=duration_seconds,
            static_duration_seconds=_parse_duration_seconds(route.get("staticDuration")),
            distance_meters=route.get("distanceMeters"),
            updated_at=datetime.now(timezone.utc),
            raw=route,
        )
