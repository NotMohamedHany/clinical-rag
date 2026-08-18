"""Thread-safe session manager for multi-user supervisor agent instances."""

from datetime import datetime, timezone
import logging
from threading import Lock
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.supervisor import build_supervisor

logger = logging.getLogger("clinical_rag.session_manager")


class SessionManager:
    """Manages active agent instances and message histories per username:session_id."""

    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def get_or_create_session(
        self, username: str, session_id: str, role: str, llm: BaseChatModel
    ) -> dict[str, Any]:
        """Fetch or initialize a session dict bound to user and session_id."""
        key = f"{username}:{session_id}"
        now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                logger.info("creating new supervisor session user=%s session_id=%s role=%s", username, session_id, role)
                session = {
                    "agent": build_supervisor(llm, key, role),
                    "messages": [],
                    "username": username,
                    "session_id": session_id,
                    "role": role,
                    "created_at": now_str,
                    "last_active": now_str,
                }
                self._sessions[key] = session
            else:
                session["last_active"] = now_str

            return session

    def list_user_sessions(self, username: str) -> list[dict[str, Any]]:
        """List active sessions for a specific user."""
        prefix = f"{username}:"
        results = []
        with self._lock:
            for key, session in self._sessions.items():
                if key.startswith(prefix):
                    results.append(
                        {
                            "session_id": session["session_id"],
                            "message_count": len(session["messages"]),
                            "created_at": session["created_at"],
                            "last_active": session["last_active"],
                            "role": session["role"],
                        }
                    )
        return sorted(results, key=lambda x: x["last_active"], reverse=True)

    def get_session_history(self, username: str, session_id: str) -> list[dict[str, str]] | None:
        """Get formatted history messages for a session."""
        key = f"{username}:{session_id}"
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            
            formatted = []
            for msg in session["messages"]:
                if isinstance(msg, HumanMessage):
                    formatted.append({"role": "user", "content": str(msg.content)})
                elif isinstance(msg, AIMessage) and msg.content:
                    formatted.append({"role": "assistant", "content": str(msg.content)})
            return formatted

    def clear_session(self, username: str, session_id: str) -> bool:
        """Remove a session from memory."""
        key = f"{username}:{session_id}"
        with self._lock:
            if key in self._sessions:
                del self._sessions[key]
                logger.info("cleared session user=%s session_id=%s", username, session_id)
                return True
            return False

    def get_active_session_count(self) -> int:
        """Return total active sessions in memory."""
        with self._lock:
            return len(self._sessions)


# Global singleton manager instance
session_manager = SessionManager()
