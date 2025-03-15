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
    model: str = Field("gemini-2.0-flash")
    model_big: str = Field("gemini-2.0-pro-exp-02-05")
    model_oai: str = Field("gpt-4o")
    embedder: str = Field("text-embedding-004")
    collection: str = Field("Arxiv")
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
    database: str = Field("", alias='PG_USER')
    user: str = Field("", alias='PG_USER')
    password: str = Field("", alias='PG_PASS')
    db_port: int = Field(5432)


class LoginSettings(BaseSettings):
    """
    Settings for login and auth
    """
    cookie_name: str = Field("", alias='COOKIE_NAME')
    auth_key: str = Field("", alias='AUTH_KEY')
    cookie_key: str = Field("", alias='COOKIE_KEY')
    cookie_expiry_days: int = Field(3, alias='COOKIE_EXPIRY_DAYS')


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
