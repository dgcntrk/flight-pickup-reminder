from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .config import Settings
from .geo import distance_meters
from .models import LocationEvidence, LocationProofResult
from .time_utils import parse_unix_timestamp, utc_now


TELEGRAM_LIVE_LOCATION_FOREVER_SECONDS = 0x7FFFFFFF


def evaluate_telegram_location(
    settings: Settings,
    location: Dict[str, Any],
    metadata: Dict[str, Any],
    now: Optional[datetime] = None,
) -> LocationProofResult:
    now = now or utc_now()
    sent_at = parse_unix_timestamp(metadata.get("date"))
    updated_at = parse_unix_timestamp(metadata.get("edit_date")) or sent_at
    live_period = _int_or_none(location.get("live_period"))
    live = live_period is not None
    active_until: Optional[datetime] = None
    if (
        sent_at
        and live_period is not None
        and live_period != TELEGRAM_LIVE_LOCATION_FOREVER_SECONDS
    ):
        active_until = sent_at + timedelta(seconds=live_period)

    active = bool(live and (active_until is None or now <= active_until))
    fresh_at = updated_at or sent_at
    fresh = bool(
        fresh_at
        and abs((now - fresh_at.astimezone(timezone.utc)).total_seconds())
        <= settings.telegram_location_max_age_minutes * 60
    )
    horizontal_accuracy = _float_or_none(location.get("horizontal_accuracy"))
    accuracy_ok = (
        horizontal_accuracy is None
        or horizontal_accuracy <= settings.telegram_location_max_accuracy_meters
    )
    movement_meters = _float_or_none(metadata.get("movement_meters"))
    moving = (
        movement_meters is not None
        and movement_meters >= settings.telegram_location_min_movement_meters
    )
    pickup_distance_meters: Optional[float] = None
    near_pickup = True
    if settings.proof_require_telegram_pickup_area:
        near_pickup = False
        if (
            settings.telegram_pickup_latitude is not None
            and settings.telegram_pickup_longitude is not None
        ):
            pickup_distance_meters = distance_meters(
                location.get("latitude"),
                location.get("longitude"),
                settings.telegram_pickup_latitude,
                settings.telegram_pickup_longitude,
            )
            near_pickup = bool(
                pickup_distance_meters is not None
                and pickup_distance_meters <= settings.telegram_pickup_radius_meters
            )

    reasons = _location_reasons(
        settings=settings,
        live=live,
        active=active,
        fresh=fresh,
        accuracy_ok=accuracy_ok,
        moving=moving,
        movement_meters=movement_meters,
        pickup_distance_meters=pickup_distance_meters,
        near_pickup=near_pickup,
    )
    accepted = (
        (live or not settings.proof_require_telegram_live_location)
        and (active or not settings.proof_require_telegram_live_location)
        and fresh
        and accuracy_ok
        and (moving or not settings.proof_require_telegram_movement)
        and (near_pickup or not settings.proof_require_telegram_pickup_area)
    )
    if accepted:
        reasons.append(
            "Telegram live location proof accepted"
            if live
            else "Telegram location proof accepted"
        )

    evidence = LocationEvidence(
        latitude=float(location.get("latitude")),
        longitude=float(location.get("longitude")),
        horizontal_accuracy=horizontal_accuracy,
        live=live,
        live_period_seconds=live_period,
        sent_at=sent_at,
        updated_at=updated_at,
        active_until=active_until,
        fresh=fresh,
        active=active,
        accuracy_ok=accuracy_ok,
        movement_meters=movement_meters,
        moving=moving,
        pickup_distance_meters=pickup_distance_meters,
        near_pickup=near_pickup,
        reasons=reasons,
    )
    return LocationProofResult(
        accepted=accepted,
        source="telegram_location",
        location=evidence,
        reasons=reasons,
    )


def _location_reasons(
    settings: Settings,
    live: bool,
    active: bool,
    fresh: bool,
    accuracy_ok: bool,
    moving: bool,
    movement_meters: Optional[float],
    pickup_distance_meters: Optional[float],
    near_pickup: bool,
) -> List[str]:
    reasons: List[str] = []
    if settings.proof_require_telegram_live_location and not live:
        reasons.append("Telegram location was static; live location is required")
    if live and not active:
        reasons.append("Telegram live location is no longer active")
    if not fresh:
        reasons.append("Telegram location update was not fresh")
    if not accuracy_ok:
        reasons.append("Telegram location accuracy was too broad")
    if settings.proof_require_telegram_movement and movement_meters is None:
        reasons.append("Telegram live location has not updated with movement yet")
    if (
        settings.proof_require_telegram_movement
        and movement_meters is not None
        and not moving
    ):
        reasons.append("Telegram live location movement was below threshold")
    if settings.proof_require_telegram_pickup_area and pickup_distance_meters is None:
        reasons.append("Telegram pickup-area geofence is not configured")
    if (
        settings.proof_require_telegram_pickup_area
        and pickup_distance_meters is not None
        and not near_pickup
    ):
        reasons.append("Telegram live location is outside the configured pickup area")
    return reasons


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
