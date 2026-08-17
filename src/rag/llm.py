"""Shared Ollama LLM helpers used by the rewriter, grader and generator."""

import time

import httpx
from langchain_ollama import ChatOllama
from ollama import ResponseError

from src import config


class OllamaUnavailableError(RuntimeError):
    """Raised when the Ollama server cannot be reached.

    Mapped to a 503 by the API layer; never shown to clients as a traceback.
    """


def get_llm(temperature: float = 0.2) -> ChatOllama:
    """Return a ChatOllama instance configured from the environment."""
    return ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=temperature,
    )


def is_ollama_available() -> bool:
    """Cheap reachability check against the Ollama server."""
    try:
        httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


# HTTP statuses worth retrying: rate limits and upstream overloads. The
# LLM is an Ollama CLOUD model, so transient errors from ollama.com are
# expected under load.
_TRANSIENT_STATUSES = {429, 500, 502, 503, 529}
_MAX_ATTEMPTS = 3
_RETRY_DELAY_S = 1.5


def _is_transient(exc: Exception) -> bool:
    """True for retryable upstream errors (rate limit / overload)."""
    if isinstance(exc, ResponseError):
        return exc.status_code in _TRANSIENT_STATUSES
    return False


def call_llm(llm, *args, **kwargs):
    """Invoke the LLM, retrying transient upstream errors with backoff.

    Connection failures are translated into OllamaUnavailableError; other
    errors propagate unchanged.
    """
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return llm.invoke(*args, **kwargs)
        except OllamaUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - classified below
            message = str(exc).lower()
            if any(
                marker in message
                for marker in ("connect", "connection", "refused", "unreachable", "timed out")
            ):
                raise OllamaUnavailableError(
                    f"Ollama is unavailable at {config.OLLAMA_BASE_URL} "
                    f"(model: {config.OLLAMA_MODEL}). Start it with `ollama serve` "
                    f"and make sure the model is pulled."
                ) from exc
            if _is_transient(exc) and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAY_S * (attempt + 1))
                continue
            raise
