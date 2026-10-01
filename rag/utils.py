from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from rag.embeddings import TEIEmbeddings
from rag.settings import settings


def get_llm():
    if settings.llm_provider == "openai":
        return get_oai_llm()
    if settings.llm_provider == "google":
        return ChatGoogleGenerativeAI(model=settings.model, temperature=settings.temperature, max_retries=2)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}, expected 'openai' or 'google'")

def get_big_llm():
    llm = ChatGoogleGenerativeAI(model=settings.model_big, temperature=settings.temperature, max_retries=2)
    return llm

def get_oai_llm():
    llm = ChatOpenAI(model=settings.model_oai, temperature=settings.temperature, max_retries=2)
    return llm


def get_embeddings():
    return TEIEmbeddings(settings.embedding_url)
