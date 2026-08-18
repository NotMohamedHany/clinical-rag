import os
from dotenv import load_dotenv
load_dotenv()


from langchain_ollama import ChatOllama

from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool

from langchain_core.output_parsers import StrOutputParser
# from langchain_tavily import TavilySearch
from src import config

_patient_llm: ChatOllama | None = None


def _get_patient_llm() -> ChatOllama:
    global _patient_llm
    if _patient_llm is None:
        _patient_llm = ChatOllama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
        )
    return _patient_llm


# TOOLS
@tool
def symptoms_checker(symptoms: str) -> str:
    """Use when need to analyze patient symptoms.
    Extracts structured information, provides safe recommendations, and includes medical disclaimers."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "1-You are a medical assistant AI that responds in English or Arabic depending on the case language.\n"
                    "2-You must always be safe, cautious, and prioritize patient well-being when analyzing patient symptoms."
                ),
            ),
            """When analyzing patient symptoms or (vital signs, measurements, labs):
1. Extract structured info: symptoms, location, duration, severity, history.
2. Provide possible causes (never absolute diagnosis).
3. Provide safe recommendations, including when to seek emergency care.
4. Always include a disclaimer: "This is not medical advice. Consult a doctor."
5. Remember to respond in the same language as the Input.

Notes:
1-Respond in the same language the input is.
2-Provide safe recommendations and possible causes with reasoning.
3-Include emergency warnings if severe symptoms are mentioned.
4-Always include the medical disclaimer.

Case:
{case}
""",
        ]
    )
    llm = _get_patient_llm()
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"case": symptoms})


# ---------------------------------------------------------------------------------------
@tool
def signs_checker(vital: str) -> str:
    """Use when need to analyze patient vital signs, measurements, or lab values.
    Provides possible clinical causes and safe recommendations with disclaimers."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "1-You are a medical assistant AI that responds in English or Arabic depending on the input language.\n"
                    "2-You must always be safe, cautious, and prioritize patient well-being."
                ),
            ),
            """When analyzing patient (vital signs, measurements, labs):
1. Extract the possible problem in patient's vital signs or labs.
2. Provide possible causes (never absolute diagnosis).
3. Provide safe recommendations, including when to seek emergency care.
4. Always include a disclaimer: "This is not medical advice. Consult a doctor."
5. Remember to respond in the same language as the Input.

Notes:
1-Respond in the same language the input is.
2-Provide safe recommendations with reasoning.
3-Include emergency warnings for critical vital signs.
4-Always include the medical disclaimer.

Input:
{input}
""",
        ]
    )
    llm = _get_patient_llm()
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"input": vital})


# ---------------------------------------------------------------------------------------

tools = [signs_checker, symptoms_checker]


