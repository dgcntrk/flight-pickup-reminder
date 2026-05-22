from datetime import datetime, time, timezone
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo

import requests

from ..config import Settings
from ..models import FlightSnapshot
from ..time_utils import parse_iso_datetime


def _airport_code(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("code_icao", "icao", "code", "code_iata", "iata"):
            item = value.get(key)
            if item:
                return str(item).upper()
    if value:
        return str(value).upper()
    return ""


def _choose_arrival(flight: Dict[str, Any]) -> Optional[datetime]:
    for key in ("actual_in", "estimated_in", "actual_on", "estimated_on", "scheduled_in", "scheduled_on"):
        parsed = parse_iso_datetime(flight.get(key))
        if parsed:
            return parsed
    return None


def _scheduled_arrival(flight: Dict[str, Any]) -> Optional[datetime]:
    for key in ("scheduled_in", "scheduled_on"):
        parsed = parse_iso_datetime(flight.get(key))
        if parsed:
            return parsed
    return None


def _actual_arrival(flight: Dict[str, Any]) -> Optional[datetime]:
    for key in ("actual_in", "actual_on"):
        parsed = parse_iso_datetime(flight.get(key))
        if parsed:
            return parsed
    return None


def _status(flight: Dict[str, Any]) -> str:
    if flight.get("cancelled"):
        return "cancelled"
    actual_off = parse_iso_datetime(flight.get("actual_off"))
    actual_on = parse_iso_datetime(flight.get("actual_on"))
    actual_in = parse_iso_datetime(flight.get("actual_in"))
    if actual_in or actual_on:
        return "arrived"
    if actual_off:
        return "enroute"
    return "scheduled"


class FlightStatusProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_snapshot(self) -> FlightSnapshot:
        if self.settings.manual_arrival_iso:
            return self._manual_snapshot()
        return self._flightaware_snapshot()

    def _manual_snapshot(self) -> FlightSnapshot:
        arrival = parse_iso_datetime(self.settings.manual_arrival_iso)
        if arrival is None:
            raise ValueError("MANUAL_ARRIVAL_ISO is not a valid ISO datetime")
        return FlightSnapshot(
            provider="manual",
            ident=self.settings.flight_ident or "manual",
            status="manual",
            arrival_eta=arrival,
            scheduled_arrival=arrival,
            actual_arrival=None,
            origin=self.settings.flight_origin_icao,
            destination=self.settings.flight_destination_icao,
            updated_at=datetime.now(timezone.utc),
            raw={"manual_arrival_iso": self.settings.manual_arrival_iso},
        )

    def _flightaware_snapshot(self) -> FlightSnapshot:
        if not self.settings.flightaware_api_key:
            raise RuntimeError("FLIGHTAWARE_API_KEY is required unless MANUAL_ARRIVAL_ISO is set")
        if not self.settings.flight_ident:
            raise RuntimeError("FLIGHT_IDENT is required unless MANUAL_ARRIVAL_ISO is set")

        url = "https://aeroapi.flightaware.com/aeroapi/flights/" + self.settings.flight_ident
        response = requests.get(
            url,
            headers={"x-apikey": self.settings.flightaware_api_key, "Accept": "application/json"},
            params={"max_pages": 1},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        flights = payload.get("flights", [])
        chosen = self._choose_flight(flights)
        if chosen is None:
            raise RuntimeError("No matching flight found for configured ident/date/route")

        origin = _airport_code(chosen.get("origin"))
        destination = _airport_code(chosen.get("destination"))
        return FlightSnapshot(
            provider="flightaware",
            ident=chosen.get("ident") or self.settings.flight_ident,
            status=_status(chosen),
            arrival_eta=_choose_arrival(chosen),
            scheduled_arrival=_scheduled_arrival(chosen),
            actual_arrival=_actual_arrival(chosen),
            origin=origin,
            destination=destination,
            updated_at=datetime.now(timezone.utc),
            raw=chosen,
        )

    def _choose_flight(self, flights: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates = []
        local_zone = ZoneInfo(self.settings.app_timezone)
        target_date = self.settings.flight_local_date
        origin = self.settings.flight_origin_icao.upper()
        destination = self.settings.flight_destination_icao.upper()

        for flight in flights:
            flight_origin = _airport_code(flight.get("origin"))
            flight_destination = _airport_code(flight.get("destination"))
            if origin and flight_origin and flight_origin != origin:
                continue
            if destination and flight_destination and flight_destination != destination:
                continue
            scheduled = _scheduled_arrival(flight) or _choose_arrival(flight)
            if target_date and scheduled:
                if scheduled.astimezone(local_zone).date().isoformat() != target_date:
                    continue
            candidates.append(flight)

        if not candidates:
            return None
        now = datetime.now(timezone.utc)

        def sort_key(item: Dict[str, Any]) -> float:
            arrival = _choose_arrival(item) or datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
            return abs((arrival - now).total_seconds())

        return sorted(candidates, key=sort_key)[0]
