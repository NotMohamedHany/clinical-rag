"""Small shared tools used by the agent scripts."""

from datetime import datetime

import requests
from langchain_core.tools import BaseTool, tool


@tool
def get_current_time() -> str:
    """Get the current date and time. Use for questions involving today/tomorrow."""
    return datetime.now().astimezone().isoformat(timespec="minutes")


# Updated with your new live n8n webhook URL
WEBHOOK_URL = "https://yacine105.app.n8n.cloud/webhook/cal-subagent"

CALENDAR_TOOL_DESCRIPTION = """Use this tool whenever the doctor wants to manage their calendar. \
This includes checking availability, booking, updating, or deleting appointments. \
Pass the doctor's exact spoken request as the 'text' string."""


def post_calendar_webhook(text: str, session_id: str) -> str:
    """Send one calendar request to the n8n calendar sub-agent."""
    payload = {
        "text": text,
        "sessionid": session_id,
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=20.0)
        # Print raw response if it fails to help debugging
        if response.status_code != 200:
            return f"HTTP Error {response.status_code}: {response.text}"

        try:
            result = response.json()
            return result.get("output", "Task completed, but no explicit output was returned.")
        except ValueError:
            return f"Received non-JSON response: {response.text}"

    except requests.exceptions.Timeout:
        return "Error: Calendar service timed out."
    except requests.exceptions.RequestException as e:
        return f"Error communicating with the Calendar Sub-Agent: {str(e)}"


@tool
def manage_calendar(text: str, session_id: str) -> str:
    """
    Use this tool whenever the doctor wants to manage their calendar.
    This includes checking availability, booking, updating, or deleting appointments.
    Pass the doctor's exact spoken request as the 'text' string.
    """
    return post_calendar_webhook(text, session_id)


def make_calendar_tool(session_id: str) -> BaseTool:
    """Build the manage_calendar tool bound to one conversation session."""

    def run(text: str) -> str:
        return post_calendar_webhook(text, session_id)

    return tool("manage_calendar", run, description=CALENDAR_TOOL_DESCRIPTION)
