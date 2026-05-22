from flight_pickup_reminder.state import StateStore


def test_state_store_round_trips_events(tmp_path) -> None:
    store = StateStore(str(tmp_path / "state.json"))

    state = store.load()
    assert state["active"] is True
    assert state["proof_accepted"] is False

    store.update(call_attempts=2, last_call_to="+16045550101")
    store.append_event("call_attempted", {"to": "+16045550101"})
    updated = store.load()

    assert updated["call_attempts"] == 2
    assert updated["last_call_to"] == "+16045550101"
    assert updated["events"][-1]["type"] == "call_attempted"
