"""Small shared tools used by the agent scripts."""

from datetime import datetime
import requests

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Get the current date and time. Use for questions involving today/tomorrow."""
    return datetime.now().astimezone().isoformat(timespec="minutes")



# Updated with your new live n8n webhook URL
WEBHOOK_URL = "https://yacine105.app.n8n.cloud/webhook/cal-subagent"

@tool
def manage_calendar(text: str,session_id:str) -> str:
    """
    Use this tool whenever the doctor wants to manage their calendar.
    This includes checking availability, booking, updating, or deleting appointments.
    Pass the doctor's exact spoken request as the 'text' string.
    """
    payload = {
        "text": text,
        "sessionid": session_id
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        # Print raw response if it fails to help debugging
        if response.status_code != 200:
            return f"HTTP Error {response.status_code}: {response.text}"
        
        try:
            result = response.json()
            return result.get("output", "Task completed, but no explicit output was returned.")
        except ValueError:
            return f"Received non-JSON response: {response.text}"

    except requests.exceptions.RequestException as e:
        return f"Error communicating with the Calendar Sub-Agent: {str(e)}"