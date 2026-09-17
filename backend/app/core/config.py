from typing import List, Union
from pydantic import Field, AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Schemora API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database — Schemora uses PostgreSQL + pgvector exclusively
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/schemora_db"

    # PostgreSQL pgvector Vector Database
    PGVECTOR_EMBEDDING_DIM: int = 768

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:5000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5000",
        "http://10.59.33.142:3000",
        "http://10.59.33.142:8000",
        "http://10.59.33.142:8080",
        "http://10.59.33.142:5000",
        "*",
    ]

    # External APIs — Groq AI
    GROQ_API_KEY: str = ""
    GROQ_GENERATION_MODEL: str = "openai/gpt-oss-20b"

    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""


settings = Settings()
