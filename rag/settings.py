from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    google_api_key: str = Field("", alias='GOOGLE_API_KEY')
    model: str = Field("gemini-2.0-flash")
    # model: str = Field("gemini-2.0-pro-exp-02-05")
    embedder: str = Field("text-embedding-004")
    collection: str = Field("Arxiv")
    json_dir: Path = Path('./rag/json_gemini/')
    temperature: float = Field(0.0)
    text_key: str = Field("page_content")
