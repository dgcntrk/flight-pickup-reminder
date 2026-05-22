import argparse
import json
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from . import mcp_tools


mcp = FastMCP("Flight Pickup Reminder", json_response=True)


@mcp.tool()
def get_pickup_setup_guide() -> Dict[str, Any]:
    """
    Get a first-time setup checklist, env template, and safe agent prompt.

    Use this before asking the user for credentials or running live checks.
    """
    return mcp_tools.get_setup_guide()


@mcp.tool()
def get_pickup_status(include_private: bool = False) -> Dict[str, Any]:
    """
    Get current flight pickup reminder state.

    State is redacted by default so an agent can reason about progress without
    seeing phone numbers, sender IDs, precise locations, or proof media paths.
    """
    return mcp_tools.get_status(include_private=include_private)


@mcp.tool()
def check_pickup_readiness() -> Dict[str, Any]:
    """Check whether the local configuration is ready for live use."""
    return mcp_tools.check_readiness()


@mcp.tool()
def preview_pickup_plan(save_to_state: bool = True, include_private: bool = False) -> Dict[str, Any]:
    """
    Compute the latest leave-by and call-start plan without placing calls.

    This may call configured flight and route providers, but it never calls
    recipients.
    """
    return mcp_tools.preview_reminder_plan(
        save_to_state=save_to_state,
        include_private=include_private,
    )


@mcp.tool()
def run_pickup_tick(
    now_iso: Optional[str] = None,
    allow_live_calls: bool = False,
    include_private: bool = False,
) -> Dict[str, Any]:
    """
    Run one reminder tick.

    By default, live calls are forced off even if the environment enables them.
    Set allow_live_calls=true only after the user explicitly asks for real calls.
    """
    return mcp_tools.run_reminder_tick(
        now_iso=now_iso,
        allow_live_calls=allow_live_calls,
        include_private=include_private,
    )


@mcp.tool()
def reset_pickup_mock_state() -> Dict[str, Any]:
    """Reset mock state when MOCK_ENABLED=true."""
    return mcp_tools.reset_mock_state()


@mcp.tool()
def record_pickup_mock_proof(accepted: bool = True) -> Dict[str, Any]:
    """Record accepted or rejected mock proof when MOCK_ENABLED=true."""
    return mcp_tools.record_mock_proof(accepted=accepted)


@mcp.resource("flight-pickup://status")
def status_resource() -> str:
    """Current redacted pickup reminder status as JSON."""
    return json.dumps(mcp_tools.get_status(include_private=False), indent=2, sort_keys=True)


@mcp.resource("flight-pickup://readiness")
def readiness_resource() -> str:
    """Current pickup reminder readiness report as JSON."""
    return json.dumps(mcp_tools.check_readiness(), indent=2, sort_keys=True)


@mcp.resource("flight-pickup://setup-guide")
def setup_guide_resource() -> str:
    """First-time setup guide and env template as JSON."""
    return json.dumps(mcp_tools.get_setup_guide(), indent=2, sort_keys=True)


@mcp.prompt()
def pickup_operator_brief(goal: str = "Check whether the pickup reminder is ready") -> str:
    """Create an agent prompt for operating the pickup reminder safely."""
    return (
        "You are helping operate Flight Pickup Reminder. Start by calling "
        "`get_pickup_setup_guide`, then `check_pickup_readiness`, then `preview_pickup_plan`, then "
        "`get_pickup_status`. Do not call `run_pickup_tick` with "
        "`allow_live_calls=true` unless the user explicitly asks you to place "
        "real calls. User goal: "
        + goal
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Flight Pickup Reminder MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport to use. Defaults to stdio for local agent clients.",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
