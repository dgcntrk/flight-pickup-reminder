from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import Settings
from .models import CallResult
from .planning import PlanningConfig, build_reminder_plan
from .providers.flightaware import FlightStatusProvider
from .providers.google_routes import RouteProvider
from .providers.twilio_gateway import TwilioGateway
from .state import StateStore
from .time_utils import parse_iso_datetime


def _plan_time(state: Dict[str, Any], name: str) -> Optional[datetime]:
    plan = state.get("plan")
    if not plan:
        return None
    if isinstance(plan, dict):
        return parse_iso_datetime(plan.get(name))
    return getattr(plan, name, None)


class ReminderOrchestrator:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        flights: FlightStatusProvider,
        routes: RouteProvider,
        twilio: TwilioGateway,
    ) -> None:
        self.settings = settings
        self.store = store
        self.flights = flights
        self.routes = routes
        self.twilio = twilio

    def tick(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        state = self.store.load()
        if state.get("opted_out"):
            self.store.append_event("tick_skipped", {"reason": "opted_out"})
            return self.store.load()
        if state.get("proof_accepted"):
            self.store.append_event("tick_skipped", {"reason": "proof_accepted"})
            return self.store.load()
        if not state.get("active", True):
            self.store.append_event("tick_skipped", {"reason": "inactive"})
            return self.store.load()

        try:
            flight = self.flights.get_snapshot()
            route = self.routes.get_snapshot()
            plan = build_reminder_plan(
                flight,
                route,
                PlanningConfig(
                    airport_arrival_buffer_minutes=self.settings.airport_arrival_buffer_minutes,
                    call_lead_minutes=self.settings.call_lead_minutes,
                ),
            )
            state.update(
                {
                    "flight": flight,
                    "route": route,
                    "plan": plan,
                    "last_error": None,
                }
            )
            self.store.save(state)

            if now >= plan.call_start_at:
                self._maybe_call(now)
            else:
                self.store.append_event(
                    "waiting",
                    {
                        "now": now.isoformat(),
                        "call_start_at": plan.call_start_at.isoformat(),
                        "leave_by": plan.leave_by.isoformat(),
                    },
                )
        except Exception as exc:
            state = self.store.update(last_error=str(exc))
            self.store.append_event("tick_error", {"error": str(exc)})
            return state
        return self.store.load()

    def call_tick(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        state = self.store.load()
        call_start_at = _plan_time(state, "call_start_at")
        if call_start_at and now >= call_start_at:
            self._maybe_call(now)
        return self.store.load()

    def _maybe_call(self, now: datetime) -> Optional[CallResult]:
        state = self.store.load()
        if state.get("proof_accepted") or state.get("opted_out"):
            return None
        attempts = int(state.get("call_attempts") or 0)
        if self.settings.max_call_attempts > 0 and attempts >= self.settings.max_call_attempts:
            self.store.append_event("call_suppressed", {"reason": "max_call_attempts", "attempts": attempts})
            return None
        if not self.settings.recipient_numbers:
            self.store.append_event("call_suppressed", {"reason": "no_recipients"})
            return None

        leave_by = _plan_time(state, "leave_by")
        if attempts > 0 and leave_by and now < leave_by:
            self.store.append_event(
                "call_waiting",
                {
                    "reason": "prep_window",
                    "seconds_until_leave_by": (leave_by - now).total_seconds(),
                    "leave_by": leave_by.isoformat(),
                },
            )
            return None

        last_call_at = parse_iso_datetime(state.get("last_call_at"))
        if last_call_at:
            elapsed = (now - last_call_at).total_seconds()
            if elapsed < self.settings.call_interval_seconds:
                self.store.append_event(
                    "call_waiting",
                    {"seconds_until_next": self.settings.call_interval_seconds - elapsed},
                )
                return None

        to_number = self.settings.recipient_numbers[attempts % len(self.settings.recipient_numbers)]
        message = self._call_message(now, leave_by)
        result = self.twilio.place_call(to_number, message)
        state["call_attempts"] = attempts + 1
        state["last_call_at"] = now.isoformat()
        state["last_call_to"] = to_number
        self.store.save(state)
        self.store.append_event(
            "call_attempted",
            {
                "to": result.to_number,
                "status": result.status,
                "sid": result.sid,
                "dry_run": result.dry_run,
                "message": result.message,
            },
        )
        return result

    def record_proof(self, proof: Any) -> Dict[str, Any]:
        state = self.store.load()
        state["proof"] = proof
        if getattr(proof, "accepted", False):
            state["proof_accepted"] = True
        self.store.save(state)
        self.store.append_event("proof_received", {"accepted": getattr(proof, "accepted", False)})
        return self.store.load()

    def _proof_instruction(self) -> str:
        if self.settings.proof_accept_telegram_location:
            return "Please head to the airport and share your live location with the Telegram bot."
        return "Please head to the airport and reply with a fresh iPhone photo from the car on the road."

    def _call_message(self, now: datetime, leave_by: Optional[datetime]) -> str:
        if leave_by and now < leave_by:
            return (
                "Pickup reminder. You have about five minutes to get ready and start driving. "
                + self._proof_instruction()
            )
        return (
            "Pickup reminder. The flight ETA and current traffic say you need to leave now. "
            + self._proof_instruction()
        )
