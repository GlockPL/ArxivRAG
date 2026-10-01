from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from rag.embeddings import TEIEmbeddings
from rag.settings import Settings


def get_llm():
    settings = Settings()
    if settings.llm_provider == "openai":
        return get_oai_llm()
    if settings.llm_provider == "google":
        return ChatGoogleGenerativeAI(model=settings.model, temperature=settings.temperature, max_retries=2)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}, expected 'openai' or 'google'")

def get_big_llm():
    settings = Settings()
    llm = ChatGoogleGenerativeAI(model=settings.model_big, temperature=settings.temperature, max_retries=2)
    return llm

def get_oai_llm():
    settings = Settings()
    llm = ChatOpenAI(model=settings.model_oai, temperature=settings.temperature, max_retries=2)
    return llm


def get_embeddings():
    settings = Settings()
    return TEIEmbeddings(settings.embedding_url)
