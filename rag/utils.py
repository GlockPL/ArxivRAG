from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI

from rag.settings import Settings


def get_llm():
    settings = Settings()
    llm = ChatGoogleGenerativeAI(model=settings.model, temperature=settings.temperature, max_retries=2)
    return llm

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
    embeddings = GoogleGenerativeAIEmbeddings(model=f"models/{settings.embedder}")
    return embeddings
