"""Streamlit chat frontend for the Clinical Guidelines RAG & Supervisor API.

Features:
- Dual-tab Auth: Login and Signup (`POST /auth/login`, `POST /auth/signup`).
- Auto-handling of 401 Unauthorized / Token expiration with clean re-authentication.
- Active Session Management: List, load history, switch, and delete sessions (`/chat/sessions`, `/chat/sessions/{id}/history`).
- Real-time SSE Streaming & Debug Modes (`POST /chat`, `POST /chat/debug`, `POST /chat/stream`).
- Modern UI with glassmorphism CSS styling, clinical quick actions, and tool trace badges.
"""

import json
import requests
import streamlit as st

st.set_page_config(
    page_title="Clinical Guidelines RAG Assistant",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_API_URL = "http://localhost:8000"
AUTH_KEYS = ("token", "username", "role", "name", "session_id")

# ---------------------------------------------------------------------------
# Custom Modern CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    .main-header {
        background: linear-gradient(90deg, #3b82f6 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        margin-bottom: 0.2rem;
    }
    
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    
    .source-pill {
        display: inline-block;
        background: rgba(59, 130, 246, 0.2);
        border: 1px solid rgba(59, 130, 246, 0.4);
        color: #60a5fa;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 500;
        margin: 3px 4px 3px 0;
    }
    
    .tool-badge {
        display: inline-block;
        background: rgba(16, 185, 129, 0.2);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-family: monospace;
    }
    
    .disclaimer-box {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
        color: #fbbf24;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API Helper Functions
# ---------------------------------------------------------------------------


def clear_auth() -> None:
    for key in (*AUTH_KEYS, "messages"):
        st.session_state.pop(key, None)


def handle_401():
    st.session_state.unauthorized_trigger = True


def api_health(api_url: str) -> dict | None:
    try:
        res = requests.get(f"{api_url}/health", timeout=5)
        return res.json()
    except requests.RequestException:
        return None


def login(api_url: str, username: str, password: str) -> dict:
    try:
        res = requests.post(
            f"{api_url}/auth/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        if res.status_code == 200:
            return res.json()
        detail = res.json().get("error", {}).get("message", f"HTTP {res.status_code}")
        return {"error": detail}
    except requests.RequestException as exc:
        return {"error": f"API unreachable: {exc}"}


def signup(api_url: str, username: str, password: str, name: str, role: str) -> dict:
    try:
        res = requests.post(
            f"{api_url}/auth/signup",
            json={"username": username, "password": password, "name": name, "role": role},
            timeout=15,
        )
        if res.status_code == 200:
            return res.json()
        detail = res.json().get("error", {}).get("message", f"HTTP {res.status_code}")
        return {"error": detail}
    except requests.RequestException as exc:
        return {"error": f"API unreachable: {exc}"}


def logout(api_url: str, token: str) -> None:
    try:
        requests.post(
            f"{api_url}/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except requests.RequestException:
        pass


def fetch_sessions(api_url: str, token: str) -> list[dict]:
    try:
        res = requests.get(
            f"{api_url}/chat/sessions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("sessions", [])
        elif res.status_code == 401:
            handle_401()
        return []
    except requests.RequestException:
        return []


def fetch_session_history(api_url: str, session_id: str, token: str) -> list[dict]:
    try:
        res = requests.get(
            f"{api_url}/chat/sessions/{session_id}/history",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("messages", [])
        elif res.status_code == 401:
            handle_401()
        return []
    except requests.RequestException:
        return []


def delete_session(api_url: str, session_id: str, token: str) -> bool:
    try:
        res = requests.delete(
            f"{api_url}/chat/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if res.status_code == 401:
            handle_401()
        return res.status_code == 200
    except requests.RequestException:
        return False


def send_chat(api_url: str, session_id: str, message: str, debug: bool, token: str) -> dict:
    endpoint = f"{api_url}/chat/debug" if debug else f"{api_url}/chat"
    try:
        res = requests.post(
            endpoint,
            json={"session_id": session_id, "message": message},
            headers={"Authorization": f"Bearer {token}"},
            timeout=300,
        )
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 401:
            handle_401()
            return {"error": "Unauthorized session"}
        detail = res.json().get("error", {}).get("message", f"HTTP {res.status_code}")
        return {"error": detail, "status": res.status_code}
    except requests.RequestException as exc:
        return {"error": f"API unreachable: {exc}"}


def send_chat_stream(api_url: str, session_id: str, message: str, token: str):
    try:
        res = requests.post(
            f"{api_url}/chat/stream",
            json={"session_id": session_id, "message": message},
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            timeout=300,
        )
        if res.status_code == 401:
            handle_401()
            yield {"error": "Unauthorized session"}
            return
        if res.status_code != 200:
            yield {"error": f"HTTP {res.status_code}"}
            return

        current_event = None
        for line in res.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("event: "):
                current_event = line_str[7:].strip()
            elif line_str.startswith("data: ") and current_event:
                data_json = json.loads(line_str[6:].strip())
                yield {"event": current_event, "data": data_json}
    except Exception as exc:
        yield {"error": str(exc)}


def clean_answer(answer: str) -> str:
    if "Sources:" in answer:
        answer = answer.split("Sources:", 1)[0]
    return answer.removeprefix("Answer:").strip()


def render_sources_pills(sources: list[dict]) -> None:
    if not sources:
        return
    pills_html = "<div><strong>📚 Guideline Citations:</strong><br/>"
    for source in sources:
        type_str = f" ({source['type']})" if source.get("type") else ""
        pills_html += f"<span class='source-pill'>📖 {source['source']} · p. {source['page']}{type_str}</span>"
    pills_html += "</div>"
    st.markdown(pills_html, unsafe_allow_html=True)


def render_debug_trace(iterations: list[dict], tool_calls: list[dict] | None = None) -> None:
    with st.expander(f"⚙️ Agent Reasoning & Multi-Tool Trace ({len(iterations)} retrieval attempt(s))"):
        if tool_calls:
            st.markdown("#### Tool Execution History")
            for call in tool_calls:
                st.markdown(
                    f"• <span class='tool-badge'>{call['tool']}</span> `args: {call['args']}`",
                    unsafe_allow_html=True,
                )
        if iterations:
            st.markdown("#### Retrieval Iterations")
            for entry in iterations:
                st.markdown(
                    f"**Iteration {entry['iteration']}** — Relevance Score: `{entry['relevance_score']:.2f}`"
                )
                st.caption(
                    f"Query: `{entry['query']}` | Hybrid Candidates: {entry['hybrid_results']} → Reranked: {entry['reranked_results']}"
                )


# Handle Unauthorized Global Trigger
if st.session_state.get("unauthorized_trigger"):
    st.session_state.pop("unauthorized_trigger", None)
    clear_auth()
    st.warning("⚠️ Session expired or server restarted. Please log in again.")
    st.rerun()

# ---------------------------------------------------------------------------
# Sidebar: Settings, Profile, Session Manager & Health
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    api_url = st.text_input("API Base URL", value=DEFAULT_API_URL)

    if st.session_state.get("token"):
        name = st.session_state["name"]
        role = st.session_state["role"]

        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        if role == "doctor":
            st.success(f"🩺 **Dr. {name}** (Doctor Role)")
            st.caption("Full Toolbox: Guidelines RAG + Calendar + Signs & Symptoms Checkers")
        else:
            st.info(f"🧑 **{name}** (Patient Role)")
            st.caption("Patient Toolbox: Guidelines RAG + Symptoms & Signs Checkers")
        st.markdown("</div>", unsafe_allow_html=True)

        # Fetch Active User Sessions
        user_sessions = fetch_sessions(api_url, st.session_state["token"])
        session_ids = [s["session_id"] for s in user_sessions]

        current_sess = st.session_state.get("session_id", "demo-1")
        if current_sess not in session_ids:
            session_ids.insert(0, current_sess)

        selected_session = st.selectbox(
            "Select Active Session",
            options=session_ids,
            index=session_ids.index(current_sess),
        )

        # Handle Session Switch
        if selected_session != st.session_state.get("session_id"):
            st.session_state.session_id = selected_session
            history = fetch_session_history(api_url, selected_session, st.session_state["token"])
            st.session_state.messages = history
            st.rerun()

        # Session Actions
        col1, col2 = st.columns(2)
        with col1:
            new_sess_input = st.text_input("New Session ID", value="sess-2", label_visibility="collapsed")
            if st.button("➕ Create", use_container_width=True):
                new_id = new_sess_input.strip() or "sess-1"
                st.session_state.session_id = new_id
                st.session_state.messages = []
                st.toast(f"Session {new_id} ready", icon="✨")
                st.rerun()

        with col2:
            if st.button("🗑️ Delete", use_container_width=True):
                delete_session(api_url, st.session_state.session_id, st.session_state["token"])
                st.session_state.session_id = "demo-1"
                st.session_state.messages = []
                st.toast("Session deleted", icon="🗑️")
                st.rerun()

        st.divider()
        debug_mode = st.toggle("🐛 Debug Trace Mode", value=False, help="Show retrieval iterations & tool trace")
        streaming_mode = st.toggle("⚡ Real-time SSE Stream", value=True, help="Stream tokens in real time")

        if st.button("🚪 Logout", use_container_width=True):
            logout(api_url, st.session_state["token"])
            clear_auth()
            st.rerun()

    st.divider()
    health = api_health(api_url)
    if health is None:
        st.error("❌ API Offline — Start uvicorn server")
    else:
        st.success(f"🟢 API Status: {health['status'].upper()} (v{health.get('version', '0.4.0')})")
        st.caption(f"🤖 LLM: `{health['llm']}`")
        st.caption(f"💾 Vector Store: `{health['vector_store']}`")
        st.caption(f"👥 Active Sessions: `{health.get('active_sessions', 0)}`")

# ---------------------------------------------------------------------------
# Auth Gate: Dual Tab Login & Signup
# ---------------------------------------------------------------------------

if not st.session_state.get("token"):
    st.markdown("<h1 class='main-header'>🩺 Clinical Guidelines Assistant</h1>", unsafe_allow_html=True)
    st.markdown("##### Agentic RAG & Clinical Decision Support System")

    tab_login, tab_signup = st.tabs(["🔒 Log In", "📝 Sign Up"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username", value="doctor")
            password = st.text_input("Password", type="password", value="doctor123")
            submit_login = st.form_submit_button("Log In", use_container_width=True)

        if submit_login:
            res = login(api_url, username, password)
            if "error" in res:
                st.error(res["error"])
            else:
                st.session_state.token = res["token"]
                st.session_state.username = res["username"]
                st.session_state.role = res["role"]
                st.session_state.name = res["name"]
                st.session_state.session_id = "demo-1"
                st.session_state.messages = []
                st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            su_username = st.text_input("Choose Username")
            su_name = st.text_input("Full Name")
            su_password = st.text_input("Choose Password", type="password")
            su_role = st.selectbox("Role", ["patient", "doctor"], index=0, help="Select clinical or patient access")
            submit_signup = st.form_submit_button("Create Account & Sign In", use_container_width=True)

        if submit_signup:
            if not su_username.strip() or not su_password.strip():
                st.error("Username and password are required")
            else:
                res = signup(api_url, su_username, su_password, su_name, su_role)
                if "error" in res:
                    st.error(res["error"])
                else:
                    st.session_state.token = res["token"]
                    st.session_state.username = res["username"]
                    st.session_state.role = res["role"]
                    st.session_state.name = res["name"]
                    st.session_state.session_id = "demo-1"
                    st.session_state.messages = []
                    st.success("Account created successfully!")
                    st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Main Chat Application Interface
# ---------------------------------------------------------------------------

st.markdown("<h1 class='main-header'>🩺 Clinical Guidelines Assistant</h1>", unsafe_allow_html=True)

st.markdown(
    "<div class='disclaimer-box'>⚠️ <strong>Educational & Research Use Only:</strong> "
    "Answers are strictly generated from guideline documents in <code>data/</code>. "
    "This system does not diagnose or prescribe. Consult a licensed clinician for medical advice.</div>",
    unsafe_allow_html=True,
)

# Quick Action Prompt Pills
st.markdown("##### 💡 Example Clinical Queries:")
q_cols = st.columns(3)
selected_prompt = None

with q_cols[0]:
    if st.button("📋 Diabetes Diagnostic Criteria", use_container_width=True):
        selected_prompt = "What are the diagnostic criteria for Type 2 Diabetes according to HEARTS-D?"
with q_cols[1]:
    if st.button("🩺 Analyze Symptoms", use_container_width=True):
        selected_prompt = "Analyze patient symptoms: high fasting blood glucose 145 mg/dL, frequent thirst, and fatigue."
with q_cols[2]:
    if st.button("📊 Evaluate Vital Signs", use_container_width=True):
        selected_prompt = "Evaluate blood pressure reading 155/95 mmHg and give guideline recommendations."

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            render_sources_pills(message["sources"])
        if message.get("iterations") or message.get("tool_calls"):
            render_debug_trace(message.get("iterations", []), message.get("tool_calls"))

# Chat Input & Processing
prompt_input = st.chat_input("Ask a clinical guideline or patient question...")
prompt = selected_prompt or prompt_input

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if streaming_mode and not debug_mode:
            message_placeholder = st.empty()
            full_response = ""
            sources = []

            with st.spinner("Streaming response..."):
                for chunk in send_chat_stream(
                    api_url, st.session_state.session_id, prompt, st.session_state["token"]
                ):
                    if "error" in chunk:
                        if chunk["error"] != "Unauthorized session":
                            st.error(chunk["error"])
                        break
                    
                    event = chunk.get("event")
                    data = chunk.get("data", {})
                    
                    if event == "token":
                        full_response += data.get("token", "")
                        message_placeholder.markdown(full_response + "▌")
                    elif event == "tool_start":
                        st.caption(f"⚙️ Invoking tool: `{data.get('tool')}`")
                    elif event == "final":
                        full_response = data.get("answer", full_response)
                        sources = data.get("sources", [])

            if full_response:
                message_placeholder.markdown(clean_answer(full_response))
                if sources:
                    render_sources_pills(sources)

                payload = {
                    "role": "assistant",
                    "content": clean_answer(full_response),
                    "sources": sources,
                }
                st.session_state.messages.append(payload)
        else:
            with st.spinner("Processing through Supervisor Agent..."):
                res = send_chat(
                    api_url,
                    st.session_state.session_id,
                    prompt,
                    debug_mode,
                    st.session_state["token"],
                )

            if "error" in res:
                if res["error"] != "Unauthorized session":
                    st.error(res["error"])
                    payload = {"role": "assistant", "content": f"⚠️ API Error: {res['error']}"}
                    st.session_state.messages.append(payload)
            else:
                payload = {
                    "role": "assistant",
                    "content": clean_answer(res["answer"]),
                    "sources": res.get("sources", []),
                    "iterations": res.get("iterations"),
                    "tool_calls": res.get("tool_calls"),
                }
                st.markdown(payload["content"])
                if payload["sources"]:
                    render_sources_pills(payload["sources"])
                if payload["iterations"] or payload["tool_calls"]:
                    render_debug_trace(payload.get("iterations", []), payload.get("tool_calls"))

                st.session_state.messages.append(payload)
