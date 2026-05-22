from datetime import datetime, timezone

from flight_pickup_reminder.geo import distance_meters
from flight_pickup_reminder.time_utils import parse_iso_datetime, parse_unix_timestamp


def test_parse_iso_datetime_accepts_zulu_and_naive_values() -> None:
    assert parse_iso_datetime("2026-05-16T17:00:00Z") == datetime(
        2026,
        5,
        16,
        17,
        0,
        tzinfo=timezone.utc,
    )
    assert parse_iso_datetime("2026-05-16T17:00:00") == datetime(
        2026,
        5,
        16,
        17,
        0,
        tzinfo=timezone.utc,
    )


def test_parse_iso_datetime_rejects_invalid_values() -> None:
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime("not-a-date") is None
    assert parse_iso_datetime(None) is None


def test_parse_unix_timestamp_normalizes_to_utc() -> None:
    assert parse_unix_timestamp(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert parse_unix_timestamp("0") == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert parse_unix_timestamp("not-a-timestamp") is None


def test_distance_meters_handles_valid_and_invalid_coordinates() -> None:
    distance = distance_meters(49.1752627, -121.9501248, 49.1753, -121.9501)

    assert distance is not None
    assert distance < 10
    assert distance_meters("bad", -121.9501248, 49.1753, -121.9501) is None
