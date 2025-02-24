from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    google_api_key: str = Field("", alias='GOOGLE_API_KEY')
    openai_api_key: str = Field("", alias='OPENAI_API_KEY')
    model: str = Field("gemini-2.0-flash")
    model_big: str = Field("gemini-2.0-pro-exp-02-05")
    model_oai: str = Field("gpt-4o")
    embedder: str = Field("text-embedding-004")
    collection: str = Field("Arxiv")
    json_dir: Path = Path('./rag/json_gemini/')
    temperature: float = Field(0.1)
    text_key: str = Field("page_content")
    # Postgresql settings
    host: str = Field("localhost")
    database: str = Field("", alias='PG_USER')
    user: str = Field("", alias='PG_USER')
    password: str = Field("", alias='PG_PASS')
    db_port: int = Field(5432)


class LoginSettings(BaseSettings):
    cookie_name: str = Field("", alias='COOKIE_NAME')
    auth_key: str = Field("", alias='AUTH_KEY')
    cookie_key: str = Field("", alias='COOKIE_KEY')
    cookie_expiry_days: int = Field(3, alias='COOKIE_EXPIRY_DAYS')
