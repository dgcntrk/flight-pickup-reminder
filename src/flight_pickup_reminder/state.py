import json
import os
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .time_utils import utc_isoformat


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.path):
                return self.default_state()
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            state = self.default_state()
            state.update(data)
            return state

    def save(self, state: Dict[str, Any]) -> None:
        with self._lock:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp_path = "{}.{}.{}.tmp".format(self.path, os.getpid(), threading.get_ident())
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(_jsonable(state), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_path, self.path)

    def update(self, **changes: Any) -> Dict[str, Any]:
        with self._lock:
            state = self.load()
            state.update(changes)
            self.save(state)
            return state

    def append_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            state = self.load()
            event = {
                "at": utc_isoformat(),
                "type": event_type,
                "payload": payload or {},
            }
            state.setdefault("events", []).append(_jsonable(event))
            state["events"] = state["events"][-200:]
            self.save(state)
            return state

    @staticmethod
    def default_state() -> Dict[str, Any]:
        return {
            "active": True,
            "opted_out": False,
            "proof_accepted": False,
            "call_attempts": 0,
            "last_call_at": None,
            "last_call_to": None,
            "last_error": None,
            "flight": None,
            "route": None,
            "plan": None,
            "proof": None,
            "telegram_location_tracks": {},
            "events": [],
        }
