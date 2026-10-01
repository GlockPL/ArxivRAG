"""
File with settings
"""
import logging
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """
    General settings like api keys and model types
    """
    google_api_key: str = Field("", alias='GOOGLE_API_KEY')
    openai_api_key: str = Field("", alias='OPENAI_API_KEY')
    model: str = Field("gemini-3.8-flash")
    model_big: str = Field("gemini-2.0-pro-exp-02-05")
    model_oai: str = Field("gpt-5.4-mini")
    # Chat model provider used by get_llm: "openai" or "google"
    llm_provider: str = Field("openai", alias='LLM_PROVIDER')
    # Local TEI embedding server, see the embeddings service in docker-compose.yml
    embedding_url: str = Field("http://localhost:8081", alias='EMBEDDING_URL')
    embedding_model: str = Field("Qwen/Qwen3-Embedding-0.6B", alias='EMBEDDING_MODEL')
    collection: str = Field("ArxivQwen3")
    json_dir: Path = Path('./json_gemini/')
    temperature: float = Field(0.1)
    text_key: str = Field("page_content")
    logging_level: int = Field(logging.DEBUG)
    weaviate_host: str = Field('localhost', alias='WEAVIATE_HOST')


class DBSettings(BaseSettings):
    """
    Settings for PostgreSQL database
    """
    host: str = Field("localhost", alias="PG_HOST")
    # Database name; defaults to the user name, which is what the postgres image creates
    database: str = Field("", alias='PG_DB')
    user: str = Field("", alias='PG_USER')
    password: str = Field("", alias='PG_PASS')
    db_port: int = Field(5432)

    def uri(self, driver: str = "postgresql") -> str:
        """Connection URI, e.g. driver="postgresql+asyncpg" for SQLAlchemy"""
        return f"{driver}://{self.user}:{self.password}@{self.host}:{self.db_port}/{self.database or self.user}"


class TokenSettings(BaseSettings):
    """
    Settings for token
    """
    secret_key: str = Field("", alias='JWT_SECRET')
    algorithm: str = Field("HS256", alias='ALGORITHM')
    token_expires_minutes: int = Field(1, alias='ACCESS_TOKEN_EXPIRE_MINUTES')
    refresh_token_expires_days: int = Field(7, alias='REFRESH_TOKEN_EXPIRE_DAYS')

class HostSettings(BaseSettings):
    """
    Settings for host values
    """
    host: str = Field("localhost", alias='HOST')
    port: int = Field(8000, alias='PORT')
    http_type: str = Field("http", alias='TYPE')

class RedisSettings(BaseSettings):
    """
    settings for redis server connection
    """
    redis_password: str = Field("", alias='REDIS_PASSWORD')
    redis_host: str = Field("localhost", alias='REDIS_HOST')
    redis_port: int = Field(6379, alias='REDIS_PORT')
    redis_db: int = Field(0, alias='REDIS_DB')


# Settings are read once from the environment and .env at import, use these instances instead of creating new ones
settings = Settings()
db_settings = DBSettings()
token_settings = TokenSettings()
host_settings = HostSettings()
redis_settings = RedisSettings()
