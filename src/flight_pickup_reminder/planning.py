from dataclasses import dataclass
from datetime import timedelta

from .models import FlightSnapshot, ReminderPlan, RouteSnapshot


@dataclass(frozen=True)
class PlanningConfig:
    airport_arrival_buffer_minutes: int
    call_lead_minutes: int


def build_reminder_plan(
    flight: FlightSnapshot,
    route: RouteSnapshot,
    config: PlanningConfig,
) -> ReminderPlan:
    if flight.arrival_eta is None:
        raise ValueError("Cannot build a reminder plan without an arrival ETA")

    airport_buffer = timedelta(minutes=config.airport_arrival_buffer_minutes)
    drive_duration = timedelta(seconds=route.duration_seconds)
    call_lead = timedelta(minutes=config.call_lead_minutes)

    target_airport_arrival_at = flight.arrival_eta - airport_buffer
    leave_by = target_airport_arrival_at - drive_duration
    call_start_at = leave_by - call_lead

    return ReminderPlan(
        arrival_eta=flight.arrival_eta,
        route_duration_seconds=route.duration_seconds,
        target_airport_arrival_at=target_airport_arrival_at,
        leave_by=leave_by,
        call_start_at=call_start_at,
        call_lead_minutes=config.call_lead_minutes,
        airport_buffer_minutes=config.airport_arrival_buffer_minutes,
    )
