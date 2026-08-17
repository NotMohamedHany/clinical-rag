"""Session-based conversation memory.

For this first version memory lives in an in-memory dictionary:

    sessions = {"session_id": [{"role": "user", "content": "..."}, ...]}

The ConversationMemory class is the only interface callers depend on, so it
can later be swapped for Redis or PostgreSQL without touching the API layer.
"""

from src.config import MAX_HISTORY_TURNS


class ConversationMemory:
    """In-memory, per-session conversation history.

    Messages are stored as {"role": "user" | "assistant", "content": str}.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = {}

    def get_history(self, session_id: str, max_turns: int = MAX_HISTORY_TURNS) -> list[dict]:
        """Return the most recent exchanges (oldest first) for a session."""
        return self._sessions.get(session_id, [])[-max_turns:]

    def add_exchange(self, session_id: str, user_message: str, assistant_message: str) -> None:
        """Record one user/assistant exchange for a session."""
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
