"""Simple Streamlit chat frontend for the Clinical Guidelines RAG API.

Run the API first (from the project root):

    uvicorn src.api.main:app --reload

Then run this frontend (from the project root):

    streamlit run frontend/app.py
"""

import requests
import streamlit as st

st.set_page_config(page_title="Clinical Guidelines RAG", page_icon="🩺", layout="centered")

DEFAULT_API_URL = "http://localhost:8000"


def api_health(api_url: str) -> dict | None:
    """GET /health; None if the API is unreachable."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.json()
    except requests.RequestException:
        return None


def send_chat(api_url: str, session_id: str, message: str, debug: bool) -> dict:
    """POST to /chat (or /chat/debug); always returns a dict."""
    endpoint = f"{api_url}/chat/debug" if debug else f"{api_url}/chat"
    try:
        response = requests.post(
            endpoint,
            json={"session_id": session_id, "message": message},
            timeout=300,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        try:
            return {"error": exc.response.json().get("detail", str(exc))}
        except ValueError:
            return {"error": str(exc)}
    except requests.RequestException as exc:
        return {"error": f"API unreachable: {exc}"}


def clean_answer(answer: str) -> str:
    """Strip the LLM's 'Answer:' / 'Sources:' scaffolding.

    The answer text is shown raw; sources are rendered separately from the
    structured API response.
    """
    if "Sources:" in answer:
        answer = answer.split("Sources:", 1)[0]
    return answer.removeprefix("Answer:").strip()


def render_sources(sources: list[dict]) -> None:
    labels = []
    for source in sources:
        label = f"{source['source']}, page {source['page']}"
        if source.get("type"):
            label = f"{source['type']} · {label}"
        labels.append(label)
    st.caption("Sources: " + ", ".join(labels))


def render_debug(iterations: list[dict], tool_calls: list[dict] | None = None) -> None:
    with st.expander(f"Supervisor trace ({len(iterations)} retrieval iteration(s))"):
        for call in tool_calls or []:
            st.markdown(f"**Tool: `{call['tool']}`**")
            st.write(f"Args: `{call['args']}`")
        for entry in iterations:
            st.markdown(
                f"**Iteration {entry['iteration']}** — "
                f"relevance score {entry['relevance_score']:.2f}"
            )
            st.write(f"Query: `{entry['query']}`")
            st.write(
                f"Hybrid results: {entry['hybrid_results']} → "
                f"reranked: {entry['reranked_results']}"
            )


# ---------------------------------------------------------------------------
# Sidebar: settings + health
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Settings")
    api_url = st.text_input("API URL", value=DEFAULT_API_URL)
    session_id = st.text_input("Session ID", value="demo-1")
    debug_mode = st.toggle("Debug mode", value=False, help="Show retrieval iterations")
    if st.button("New session", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    health = api_health(api_url)
    if health is None:
        st.error("API unreachable — is uvicorn running?")
    else:
        st.success(f"API status: {health['status']}")
        st.caption(f"LLM: {health['llm']}")
        st.caption(f"Vector store: {health['vector_store']}")

# ---------------------------------------------------------------------------
# Main chat
# ---------------------------------------------------------------------------

st.title("🩺 Clinical Guidelines Assistant")
st.caption(
    "Answers come from the clinical guidelines in `data/`. "
    "Educational use only — not medical advice."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            render_sources(message["sources"])
        if message.get("iterations"):
            render_debug(message["iterations"], message.get("tool_calls"))

if prompt := st.chat_input("Ask a question about the guideline..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving evidence and generating the answer..."):
            result = send_chat(api_url, session_id, prompt, debug_mode)

        if "error" in result:
            st.error(result["error"])
            payload = {"role": "assistant", "content": f"⚠️ API error: {result['error']}"}
        else:
            payload = {
                "role": "assistant",
                "content": clean_answer(result["answer"]),
                "sources": result.get("sources", []),
                "iterations": result.get("iterations"),
                "tool_calls": result.get("tool_calls"),
            }
            st.markdown(payload["content"])
            if payload["sources"]:
                render_sources(payload["sources"])
            if payload["iterations"]:
                render_debug(payload["iterations"], payload["tool_calls"])

    st.session_state.messages.append(payload)
