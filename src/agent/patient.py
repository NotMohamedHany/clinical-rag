import os
from dotenv import load_dotenv
load_dotenv()


from langchain_ollama import ChatOllama

from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool

from langchain_core.output_parsers import StrOutputParser
# from langchain_tavily import TavilySearch
from src import config

#TOOLS
@tool
def symptoms_checker(symptoms:str) -> str:
    """Use when need to analyze  symptoms
get information about the symptoms and give some recommendations and possible causes input query (string) is the patient data or symptoms """
    prompt=ChatPromptTemplate.from_messages([
    ("system",("1-You are a medical assistant AI that respond in the english or arabic language only depending on Case language."
               "2-You must always be safe, cautious, and prioritize patient well-being When analyzing patient symptoms ")),
    """When analyzing patient symptoms or (vital signs, measurements, labs):
1. Extract structured info: symptoms, location, duration, severity, history.(if it in the case and its possible)
2. Provide possible causes (never absolute diagnosis).
3. Provide safe recommendations, including when to seek emergency care.
4. Always include a disclaimer: "This is not medical advice. Consult a doctor."
5. Remember to respond in the same language as the Input.

Notes:
1-respond in the same language the input is
1-Just respond with possible causes with the reasoning and the safe recommendations.
2-must give some safe recommendations
3-dont forget any step of analyzing
4-dont forget the disclaimer and the recommendation
5-dont overtalk
6- if u dont have a recommendation say :"recommend Consult a doctor "

Case:
{case}
"""])
    print("111111111111111111111111")
    llm=ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )
    chain=prompt|llm|StrOutputParser()
    return chain.invoke(symptoms)
#---------------------------------------------------------------------------------------
@tool
def signs_checker(vital:str) -> str:
    """Use when need to analyze (vital signs, measurements, labs)s
    get information about the patient's (vital signs, measurements, labs)s and give some recommendations and possible causes input query (string) is the patient data or symptoms  """
    prompt=ChatPromptTemplate.from_messages([
    ("system",("1-You are a medical assistant AI that respond in the english or arabic language only depending on Case language."
               "2-You must always be safe, cautious, and prioritize patient well-being When analyzing patient symptoms ")),
    """When analyzing patient (vital signs, measurements, labs):
1. Extract the possible problem in patient's (vital signs, measurements, labs) .
2. Provide possible causes (never absolute diagnosis).
3. Provide safe recommendations, including when to seek emergency care.
4. Always include a disclaimer: "This is not medical advice. Consult a doctor."
5-remember to respond in the same language as the Input.

Notes:
1-respond in the same language the input is
1-Just respond with possible causes with the reasoning and the safe recommendations.
2-must give some safe recommendations
3-dont forget any step of analyzing
4-dont forget the disclaimer and the recommendation
5-dont overtalk
6- if u dont have a recommendation say :"recommend Consult a doctor "

Input:
{input}
"""])
    print("22222222222222222222222222")
    llm=ChatOllama(
        model=config.OLLAMA_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )
    chain=prompt|llm|StrOutputParser()
    return chain.invoke(vital)

#---------------------------------------------------------------------------------------


# tavily_search_tool = TavilySearch(
#     max_results=5,
#     topic="general",
# )

tools=[signs_checker,symptoms_checker]


