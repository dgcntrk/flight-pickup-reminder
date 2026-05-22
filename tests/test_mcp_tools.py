from flight_pickup_reminder import mcp_tools
from flight_pickup_reminder.state import StateStore


def test_mcp_status_redacts_private_fields(settings):
    store = StateStore(settings.state_path)
    state = store.default_state()
    state["last_call_to"] = "+16045550101"
    state["events"] = [{"type": "call_attempted", "payload": {"to": "+16045550101", "sender_id": 1234}}]
    store.save(state)

    status = mcp_tools.get_status(settings=settings)

    assert status["last_call_to"] == "[redacted]"
    assert status["events"][0]["payload"]["to"] == "[redacted]"
    assert status["events"][0]["payload"]["sender_id"] == "[redacted]"


def test_mcp_setup_guide_includes_template_and_readiness(settings):
    guide = mcp_tools.get_setup_guide(settings=settings)

    assert "dotenv_template" in guide
    assert "CALLING_ENABLED=false" in guide["dotenv_template"]
    assert "Twilio account" in guide["minimum_live_accounts"][0]
    assert guide["readiness"]["ready_for_live"] is False


def test_mcp_preview_plan_computes_without_calls(settings):
    result = mcp_tools.preview_reminder_plan(settings=settings)

    assert result["ok"] is True
    assert result["flight"]["provider"] == "manual"
    assert result["route"]["provider"] == "manual"
    assert result["plan"]["leave_by"] == "2026-05-16T09:20:00-07:00"


def test_mcp_run_tick_forces_dry_run_unless_live_calls_are_allowed(settings_factory):
    settings = settings_factory(calling_enabled=True)

    state = mcp_tools.run_reminder_tick(
        now_iso="2026-05-16T16:15:00Z",
        settings=settings,
        include_private=True,
    )

    assert state["call_attempts"] == 1
    assert state["events"][-1]["type"] == "call_attempted"
    assert state["events"][-1]["payload"]["dry_run"] is True
    assert state["events"][-1]["payload"]["message"] == "CALLING_ENABLED=false"


def test_mcp_mock_proof_requires_mock_enabled(settings_factory):
    settings = settings_factory(mock_enabled=False)

    try:
        mcp_tools.record_mock_proof(settings=settings)
    except ValueError as exc:
        assert "MOCK_ENABLED" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_mcp_mock_proof_records_acceptance(settings):
    state = mcp_tools.record_mock_proof(settings=settings)

    assert state["proof_accepted"] is True
    assert state["proof"]["accepted"] is True
