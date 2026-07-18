"""Application settings loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Application ----
    APP_NAME: str = "CORE FIGHTER"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default_factory=list)

    # ---- Security ----
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30
    ENCRYPTION_KEY: str = ""

    # ---- Database ----
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "corefighter"
    POSTGRES_PASSWORD: str = "corefighter"
    POSTGRES_DB: str = "corefighter"

    # ---- Redis ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ---- Object storage ----
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "corefighter-media"
    S3_PUBLIC_URL: str = "http://localhost:9000/corefighter-media"
    S3_USE_SSL: bool = False

    # ---- OpenAI ----
    OPENAI_API_KEY: str = ""
    OPENAI_VISION_MODEL: str = "gpt-4o"
    OPENAI_TEXT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIM: int = 1536
    # Generation tuning (buyersbox EXPERIENCE style)
    OPENAI_TEMPERATURE: float = 0.55
    OPENAI_MAX_TOKENS: int = 1200
    OPENAI_FREQUENCY_PENALTY: float = 0.25
    OPENAI_PRESENCE_PENALTY: float = 0.15
    OPENAI_TOP_P: float = 0.9

    # ---- Jobs ----
    JOB_MAX_ATTEMPTS: int = 3
    JOB_RETRY_DELAY_SECONDS: int = 30

    # ---- Similarity ----
    SIMILARITY_THRESHOLD: float = 0.50

    # ---- Seed admin ----
    FIRST_ADMIN_EMAIL: str = "admin@corefighter.local"
    FIRST_ADMIN_PASSWORD: str = "admin12345"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Used by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_settings(self) -> dict:
        return {
            "host": self.REDIS_HOST,
            "port": self.REDIS_PORT,
            "database": self.REDIS_DB,
            "password": self.REDIS_PASSWORD or None,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
