"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import asyncio
import logging
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.memory.mutations import MemoryMutationError

from backend.api.auth import router as auth_router
from backend.api.chat import router as chat_router
from backend.api.memory_debug import router as memory_debug_router
from backend.api.profile import router as profile_router
from backend.config import Settings, get_settings
from backend.database.chroma_repository import ChromaChatRepository
from backend.database.factory import create_repository
from backend.llm.fallback_client import FallbackLlmClient
from backend.llm.groq_client import GroqClient
from backend.llm.ollama_client import OllamaClient
from backend.services.chat_service import ChatService
from backend.memory.semantic_chat import SemanticChatMemory
from backend.services.profile_service import ProfileService
from backend.utils.email_service import EmailService
from backend.utils.local_endpoints import validate_model_endpoints


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API and wire its dependencies.

    Passing settings explicitly keeps tests isolated and makes future deployment
    configuration straightforward.
    """

    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        validate_model_endpoints(app_settings)
        repository = create_repository(app_settings)
        ollama_client = (
            OllamaClient(
                app_settings.ollama_base_url,
                app_settings.ollama_model,
                keep_alive=app_settings.ollama_keep_alive,
                num_predict=app_settings.ollama_num_predict,
            )
            if app_settings.ollama_base_url
            else None
        )
        llm_client = ollama_client
        if app_settings.groq_api_key:
            groq_client = GroqClient(
                api_key=app_settings.groq_api_key,
                model=app_settings.groq_model,
                base_url=app_settings.groq_base_url,
                num_predict=app_settings.groq_num_predict,
            )
            llm_client = FallbackLlmClient(
                primary=groq_client,
                fallback=ollama_client,
            )
        if app_settings.lmstudio_base_url:
            llm_client = GroqClient(
                api_key="local", model=app_settings.lmstudio_model,
                base_url=app_settings.lmstudio_base_url, num_predict=700,
                temperature=0.1,
            )
        semantic_memory = SemanticChatMemory(
            repository, app_settings.lmstudio_base_url, app_settings.embedding_model,
        )
        if app_settings.memory_configuration not in {'vector', 'hybrid'}:
            semantic_memory = None
        repository.semantic_memory = semantic_memory
        graph_memory = None
        if app_settings.graph_enabled:
            from backend.memory.graph_memory import Neo4jMemory
            credentials = json.loads(app_settings.graph_credentials_file.read_text())
            graph_memory = Neo4jMemory(repository, app_settings.graph_uri,
                                       credentials['username'], credentials['password'],
                                       app_settings.graph_database)
            repository.graph_memory = graph_memory
        repository.mutations.resume()
        if graph_memory is not None:graph_memory.backfill_all()
        app.state.chat_service = ChatService(
            repository,
            llm_client,
            working_memory_limit=app_settings.working_memory_message_limit,
            semantic_memory=semantic_memory,
            prompt_token_budget=app_settings.prompt_token_budget,
            memory_min_similarity=app_settings.memory_min_similarity,
            memory_configuration=app_settings.memory_configuration,
            graph_memory=graph_memory,
        )
        app.state.profile_service = ProfileService(
            repository,
            EmailService(app_settings),
        )
        async def expire_idle_sessions():
            while True:
                try:
                    await asyncio.to_thread(repository.mutations.resume)
                    await asyncio.to_thread(repository.session_memory.expire)
                except Exception:
                    logging.getLogger(__name__).exception('Session forgetting failed; will retry')
                await asyncio.sleep(30)

        await asyncio.to_thread(repository.session_memory.expire)
        cleanup = asyncio.create_task(expire_idle_sessions())
        try:
            yield
        finally:
            cleanup.cancel()
            try:
                await cleanup
            except asyncio.CancelledError:
                pass
            if graph_memory is not None:
                graph_memory.close()
            if getattr(repository,'sql_store',None) is not None:
                repository.sql_store.close()

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Local-first API for the ChatbotTutorAI research platform.",
        lifespan=lifespan,
    )
    @app.exception_handler(MemoryMutationError)
    async def mutation_unavailable(request,error):
        return JSONResponse(status_code=503,content={'detail':str(error)})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(chat_router)
    app.include_router(memory_debug_router)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()
