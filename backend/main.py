"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router as chat_router
from backend.config import Settings, get_settings
from backend.database.chroma_repository import ChromaChatRepository
from backend.llm.groq_client import GroqClient
from backend.services.chat_service import ChatService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API and wire its dependencies.

    Passing settings explicitly keeps tests isolated and makes future deployment
    configuration straightforward.
    """

    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repository = ChromaChatRepository(app_settings.chroma_path)
        llm_client = (
            GroqClient(app_settings.api_key, app_settings.groq_model)
            if app_settings.api_key
            else None
        )
        app.state.chat_service = ChatService(repository, llm_client)
        yield

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Local-first API for the ChatbotTutorAI research platform.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()
