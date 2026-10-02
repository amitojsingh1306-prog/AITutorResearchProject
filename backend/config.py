"""Environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings with local-development defaults."""

    app_name: str = "ChatbotTutorAI API"
    chroma_path: Path = PROJECT_ROOT / "chroma_db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "CHATBOT_GROQ_API_KEY"),
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("GROQ_BASE_URL", "CHATBOT_GROQ_BASE_URL"),
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias=AliasChoices("GROQ_MODEL", "CHATBOT_GROQ_MODEL"),
    )
    groq_num_predict: int = Field(
        default=700,
        validation_alias=AliasChoices("GROQ_NUM_PREDICT", "CHATBOT_GROQ_NUM_PREDICT"),
    )
    ollama_base_url: str | None = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "CHATBOT_OLLAMA_BASE_URL"),
    )
    ollama_model: str = Field(
        default="qwen2.5:1.5b",
        validation_alias=AliasChoices("OLLAMA_MODEL", "CHATBOT_OLLAMA_MODEL"),
    )
    ollama_keep_alive: str = Field(
        default="30m",
        validation_alias=AliasChoices("OLLAMA_KEEP_ALIVE", "CHATBOT_OLLAMA_KEEP_ALIVE"),
    )
    ollama_num_predict: int = Field(
        default=700,
        validation_alias=AliasChoices("OLLAMA_NUM_PREDICT", "CHATBOT_OLLAMA_NUM_PREDICT"),
    )
    working_memory_message_limit: int = 10
    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST", "CHATBOT_SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "CHATBOT_SMTP_PORT"),
    )
    smtp_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME", "CHATBOT_SMTP_USERNAME"),
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "CHATBOT_SMTP_PASSWORD"),
    )
    smtp_from_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "CHATBOT_SMTP_FROM_EMAIL"),
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_USE_TLS", "CHATBOT_SMTP_USE_TLS"),
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="CHATBOT_",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for the default application."""

    return Settings()
