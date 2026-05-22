from datetime import datetime, timedelta, timezone

from flight_pickup_reminder.models import FlightSnapshot, RouteSnapshot
from flight_pickup_reminder.planning import PlanningConfig, build_reminder_plan


def test_build_reminder_plan_calls_five_minutes_before_leave_time() -> None:
    arrival = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
    flight = FlightSnapshot(
        provider="test",
        ident="F8701",
        status="enroute",
        arrival_eta=arrival,
        scheduled_arrival=arrival,
        actual_arrival=None,
        origin="CYEG",
        destination="CYXX",
        updated_at=arrival,
    )
    route = RouteSnapshot(
        provider="test",
        duration_seconds=35 * 60,
        static_duration_seconds=None,
        distance_meters=None,
        updated_at=arrival,
    )

    plan = build_reminder_plan(
        flight,
        route,
        PlanningConfig(airport_arrival_buffer_minutes=5, call_lead_minutes=5),
    )

    assert plan.target_airport_arrival_at == arrival - timedelta(minutes=5)
    assert plan.leave_by == arrival - timedelta(minutes=40)
    assert plan.call_start_at == arrival - timedelta(minutes=45)


def test_build_reminder_plan_requires_arrival_eta() -> None:
    flight = FlightSnapshot(
        provider="test",
        ident="F8701",
        status="scheduled",
        arrival_eta=None,
        scheduled_arrival=None,
        actual_arrival=None,
        origin="CYEG",
        destination="CYXX",
        updated_at=datetime.now(timezone.utc),
    )
    route = RouteSnapshot(
        provider="test",
        duration_seconds=1800,
        static_duration_seconds=None,
        distance_meters=None,
        updated_at=datetime.now(timezone.utc),
    )

    try:
        build_reminder_plan(
            flight,
            route,
            PlanningConfig(airport_arrival_buffer_minutes=5, call_lead_minutes=5),
        )
    except ValueError as exc:
        assert "arrival ETA" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
