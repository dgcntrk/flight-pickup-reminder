from datetime import datetime, timedelta, timezone

from flight_pickup_reminder.mock import mock_proof
from flight_pickup_reminder.models import CallResult, FlightSnapshot, RouteSnapshot
from flight_pickup_reminder.orchestrator import ReminderOrchestrator
from flight_pickup_reminder.state import StateStore


class StaticFlightProvider:
    def __init__(self, arrival):
        self.arrival = arrival

    def get_snapshot(self):
        return FlightSnapshot(
            provider="test",
            ident="MOCK-FLAIR-YEG-YXX",
            status="scheduled",
            arrival_eta=self.arrival,
            scheduled_arrival=self.arrival,
            actual_arrival=None,
            origin="CYEG",
            destination="CYXX",
            updated_at=self.arrival,
        )


class StaticRouteProvider:
    def __init__(self, duration_seconds):
        self.duration_seconds = duration_seconds

    def get_snapshot(self):
        return RouteSnapshot(
            provider="test",
            duration_seconds=self.duration_seconds,
            static_duration_seconds=None,
            distance_meters=None,
            updated_at=datetime.now(timezone.utc),
        )


class RecordingCallGateway:
    def __init__(self):
        self.calls = []

    def place_call(self, to_number, message):
        self.calls.append((to_number, message))
        return CallResult(
            to_number=to_number,
            provider="test",
            sid="CA{}".format(len(self.calls)),
            status="queued",
            dry_run=True,
            message="recorded",
        )


def make_orchestrator(settings):
    arrival = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
    gateway = RecordingCallGateway()
    store = StateStore(settings.state_path)
    store.save(StateStore.default_state())
    orchestrator = ReminderOrchestrator(
        settings=settings,
        store=store,
        flights=StaticFlightProvider(arrival),
        routes=StaticRouteProvider(35 * 60),
        twilio=gateway,
    )
    return orchestrator, store, gateway, arrival


def test_tick_calls_when_call_window_opens(settings):
    orchestrator, store, gateway, arrival = make_orchestrator(settings)
    call_start = arrival - timedelta(minutes=45)

    state = orchestrator.tick(now=call_start)

    assert state["call_attempts"] == 1
    assert state["last_call_to"] == "+16045550101"
    assert gateway.calls[0][0] == "+16045550101"
    assert store.load()["events"][-1]["type"] == "call_attempted"


def test_tick_suppresses_repeat_calls_during_lead_window(settings):
    orchestrator, _, gateway, arrival = make_orchestrator(settings)
    call_start = arrival - timedelta(minutes=45)
    leave_by = call_start + timedelta(minutes=5)

    orchestrator.tick(now=call_start)
    orchestrator.tick(now=call_start + timedelta(seconds=10))
    orchestrator.tick(now=call_start + timedelta(seconds=30))
    orchestrator.tick(now=leave_by)

    assert [call[0] for call in gateway.calls] == ["+16045550101", "+16045550102"]
    assert "five minutes to get ready" in gateway.calls[0][1]


def test_after_leave_by_respects_interval_and_alternates_numbers(settings):
    orchestrator, _, gateway, arrival = make_orchestrator(settings)
    call_start = arrival - timedelta(minutes=45)
    leave_by = call_start + timedelta(minutes=5)

    orchestrator.tick(now=call_start)
    orchestrator.tick(now=leave_by)
    orchestrator.tick(now=leave_by + timedelta(seconds=10))
    orchestrator.tick(now=leave_by + timedelta(seconds=30))

    assert [call[0] for call in gateway.calls] == [
        "+16045550101",
        "+16045550102",
        "+16045550101",
    ]
    assert "need to leave now" in gateway.calls[1][1]


def test_call_tick_uses_existing_plan_without_refetching_route(settings):
    orchestrator, _, gateway, arrival = make_orchestrator(settings)
    call_start = arrival - timedelta(minutes=45)

    orchestrator.tick(now=call_start - timedelta(minutes=1))
    orchestrator.call_tick(now=call_start)

    assert [call[0] for call in gateway.calls] == ["+16045550101"]


def test_accepted_proof_stops_later_calls(settings):
    orchestrator, store, gateway, arrival = make_orchestrator(settings)
    orchestrator.record_proof(mock_proof(True))

    state = orchestrator.tick(now=arrival)

    assert state["proof_accepted"] is True
    assert gateway.calls == []
    assert store.load()["events"][-1]["payload"]["reason"] == "proof_accepted"


def test_max_attempts_suppresses_additional_calls(settings_factory):
    settings = settings_factory(max_call_attempts=1)
    orchestrator, store, gateway, arrival = make_orchestrator(settings)
    call_start = arrival - timedelta(minutes=45)

    orchestrator.tick(now=call_start)
    orchestrator.tick(now=call_start + timedelta(seconds=31))

    assert len(gateway.calls) == 1
    assert store.load()["events"][-1]["type"] == "call_suppressed"
