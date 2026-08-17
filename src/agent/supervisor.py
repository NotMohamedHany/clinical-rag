"""The supervisor agent: RAG pipeline + calendar webhook as its toolbox.

One agent (the same Ollama model) decides per question which tool to call:
clinical_guidelines (the whole RAG pipeline as one tool) for medical
questions, manage_calendar (n8n webhook) for scheduling. Both tools are
bound to the conversation's session_id, so per-session memory works end to
end. The supervisor's own messages list is kept per session by the caller
(the API layer) for follow-up context.
"""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from src.agent.tools import get_current_time, make_calendar_tool
from src.rag.rag_tool import clinical_guidelines_tool

SYSTEM_PROMPT = """You are a clinical assistant supervisor. You have these tools:

1. clinical_guidelines(question) - answers medical/clinical questions
   strictly from the guideline PDFs in data/ (diabetes, osteoporosis, ...).
   Returns JSON with "answer", "sources" and "retrieval". Always use it for
   anything about diagnosis, treatment, management, screening or dosing.
2. manage_calendar(text) - manages the doctor's calendar (availability,
   booking, updating, deleting appointments). Pass the doctor's exact
   request as text.
3. get_current_time() - current date and time; call it before calendar
   questions that mention today/tomorrow.

Rules:
- For medical questions, restate the clinical_guidelines answer faithfully
  and keep its source citations. If it says the guidelines lack the
  information, say so - never invent medical facts.
- For combined requests, call both tools.
- Answer concisely."""


def build_supervisor(llm: BaseChatModel, session_id: str):
    """Compile the supervisor agent with tools bound to one session."""
    tools = [
        clinical_guidelines_tool(session_id),
        make_calendar_tool(session_id),
        get_current_time,
    ]
    return create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)
