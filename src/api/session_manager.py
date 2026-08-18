"""Thread-safe session manager for multi-user supervisor agent instances with disk persistence."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from src import config
from src.agent.supervisor import build_supervisor

logger = logging.getLogger("clinical_rag.session_manager")

SESSION_TTL_SECONDS = 86400  # 24 hours
SESSIONS_DIR = config.DATA_DIR / "sessions"


class SessionManager:
    """Manages active agent instances and message histories per username:session_id with disk persistence."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, username: str, session_id: str) -> Path:
        safe_user = username.replace("/", "_").replace("\\", "_")
        safe_sess = session_id.replace("/", "_").replace("\\", "_")
        return SESSIONS_DIR / f"{safe_user}__{safe_sess}.json"

    def _serialize_messages(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        serialized = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized.append({"type": "human", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                if msg.content:
                    serialized.append({"type": "ai", "content": str(msg.content)})
            elif isinstance(msg, ToolMessage):
                serialized.append({"type": "tool", "content": str(msg.content), "name": getattr(msg, "name", "")})
        return serialized

    def _deserialize_messages(self, data: list[dict[str, str]]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for item in data:
            mtype = item.get("type")
            content = item.get("content", "")
            if mtype == "human":
                messages.append(HumanMessage(content=content))
            elif mtype == "ai":
                messages.append(AIMessage(content=content))
            elif mtype == "tool":
                messages.append(ToolMessage(content=content, name=item.get("name", "tool"), tool_call_id="saved"))
        return messages

    def save_session_to_disk(self, username: str, session_id: str) -> None:
        """Persist session state and history to disk."""
        key = f"{username}:{session_id}"
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return
            
            filepath = self._get_file_path(username, session_id)
            try:
                payload = {
                    "username": username,
                    "session_id": session_id,
                    "role": session["role"],
                    "created_at": session["created_at"],
                    "last_active": session["last_active"],
                    "messages": self._serialize_messages(session["messages"]),
                }
                with filepath.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
            except Exception as exc:
                logger.error("failed to save session to disk key=%s error=%s", key, exc)

    def _load_session_from_disk_unlocked(
        self, username: str, session_id: str, llm: BaseChatModel | None = None
    ) -> dict[str, Any] | None:
        filepath = self._get_file_path(username, session_id)
        if not filepath.exists():
            return None

        try:
            with filepath.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            
            key = f"{username}:{session_id}"
            role = data.get("role", "doctor")
            messages = self._deserialize_messages(data.get("messages", []))
            
            agent = build_supervisor(llm, key, role) if llm else None

            session = {
                "agent": agent,
                "messages": messages,
                "username": username,
                "session_id": session_id,
                "role": role,
                "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
                "last_active": data.get("last_active", datetime.now(timezone.utc).isoformat()),
            }
            self._sessions[key] = session
            return session
        except Exception as exc:
            logger.error("failed to load session from disk filepath=%s error=%s", filepath, exc)
            return None

    def _cleanup_stale_unlocked(self) -> None:
        """Evict sessions inactive longer than TTL."""
        now = datetime.now(timezone.utc)
        stale_keys = []
        for key, session in self._sessions.items():
            try:
                last_dt = datetime.fromisoformat(session["last_active"])
                if (now - last_dt).total_seconds() > self._ttl_seconds:
                    stale_keys.append(key)
            except Exception:
                pass
        for key in stale_keys:
            del self._sessions[key]
            logger.info("evicted stale session key=%s", key)

    def get_or_create_session(
        self, username: str, session_id: str, role: str, llm: BaseChatModel
    ) -> dict[str, Any]:
        """Fetch or initialize a session dict bound to user and session_id."""
        key = f"{username}:{session_id}"
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat(timespec="seconds")

        with self._lock:
            self._cleanup_stale_unlocked()
            session = self._sessions.get(key)

            if session is None:
                session = self._load_session_from_disk_unlocked(username, session_id, llm)

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
                if session.get("agent") is None and llm:
                    session["agent"] = build_supervisor(llm, key, role)
                session["last_active"] = now_str

            return session

    def list_user_sessions(self, username: str) -> list[dict[str, Any]]:
        """List active and persisted sessions for a specific user."""
        prefix = f"{username}:"
        results_map: dict[str, dict[str, Any]] = {}

        with self._lock:
            for key, session in self._sessions.items():
                if key.startswith(prefix):
                    results_map[session["session_id"]] = {
                        "session_id": session["session_id"],
                        "message_count": len(session["messages"]),
                        "created_at": session["created_at"],
                        "last_active": session["last_active"],
                        "role": session["role"],
                    }

            safe_user = username.replace("/", "_").replace("\\", "_")
            pattern = f"{safe_user}__*.json"
            for filepath in SESSIONS_DIR.glob(pattern):
                try:
                    sess_id = filepath.name.removeprefix(f"{safe_user}__").removesuffix(".json")
                    if sess_id not in results_map:
                        with filepath.open("r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        results_map[sess_id] = {
                            "session_id": sess_id,
                            "message_count": len(data.get("messages", [])),
                            "created_at": data.get("created_at", ""),
                            "last_active": data.get("last_active", ""),
                            "role": data.get("role", "doctor"),
                        }
                except Exception as exc:
                    logger.warning("failed reading session file %s: %s", filepath, exc)

        results = list(results_map.values())
        return sorted(results, key=lambda x: x["last_active"], reverse=True)

    def get_session_history(self, username: str, session_id: str) -> list[dict[str, str]] | None:
        """Get formatted history messages for a session."""
        key = f"{username}:{session_id}"
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = self._load_session_from_disk_unlocked(username, session_id)
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
        """Remove a session from memory and disk."""
        key = f"{username}:{session_id}"
        with self._lock:
            removed = False
            if key in self._sessions:
                del self._sessions[key]
                removed = True
            filepath = self._get_file_path(username, session_id)
            if filepath.exists():
                try:
                    filepath.unlink()
                    removed = True
                except Exception as exc:
                    logger.error("failed deleting session file %s: %s", filepath, exc)
            if removed:
                logger.info("cleared session user=%s session_id=%s", username, session_id)
            return removed

    def get_active_session_count(self) -> int:
        """Return total active sessions in memory and disk."""
        with self._lock:
            disk_count = len(list(SESSIONS_DIR.glob("*.json")))
            return max(len(self._sessions), disk_count)


# Global singleton manager instance
session_manager = SessionManager()

