"""Chat lifecycle and messaging endpoints."""

from typing import Annotated
from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, Header, status, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from backend.ocr.local_ocr import LocalOCR, OCRError, SUPPORTED_SUFFIXES

from backend.api.dependencies import get_chat_service
from backend.models.chat import (
    ChatCreateRequest,
    ChatDetail,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummary,
    MessageUpdateRequest,
    ForgetRequest,
    Message,
)
from backend.services.chat_service import ChatService


router = APIRouter(prefix="/chat", tags=["chat"])
ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
UserIdHeader = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=120)]


@router.post(
    "/create",
    response_model=ChatSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_chat(
    payload: ChatCreateRequest,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatSummary:
    """Create an empty conversation."""

    return service.create_chat(payload, user_id)


@router.get("/list", response_model=list[ChatSummary])
def list_chats(service: ChatServiceDependency, user_id: UserIdHeader) -> list[ChatSummary]:
    """List conversations, most recently updated first."""

    return service.list_chats(user_id)


@router.get("/{chat_id}", response_model=ChatDetail)
def get_chat(
    chat_id: str,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatDetail:
    """Return one conversation and its ordered messages."""

    return service.get_chat(chat_id, user_id)


@router.post(
    "/{chat_id}/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    chat_id: str,
    payload: ChatMessageRequest,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> ChatMessageResponse:
    """Store a user message and the Phase 1 placeholder assistant reply."""

    return service.add_message(chat_id, payload, user_id)


@router.post("/{chat_id}/message/stream")
def stream_message(
    chat_id: str,
    payload: ChatMessageRequest,
    service: ChatServiceDependency,
    user_id: UserIdHeader,
) -> StreamingResponse:
    """Store a user message and stream the assistant reply as it is generated."""

    service.get_chat(chat_id, user_id)
    if payload.image_id:
        try:
            service._repository.session_memory.get_image(user_id, chat_id, payload.image_id)
        except LookupError as error:
            raise HTTPException(404, str(error)) from error

    return StreamingResponse(
        service.stream_message(chat_id, payload, user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post('/{chat_id}/images', status_code=201)
async def upload_image(chat_id: str, request: Request, service: ChatServiceDependency,
                       user_id: UserIdHeader, filename: str = Query(min_length=1, max_length=255)):
    """Read bounded image bytes, perform local OCR, and save in this chat's session."""
    service.get_chat(chat_id, user_id)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(415, 'Use a PNG, JPEG, TIFF, BMP or WebP image.')
    limit = 25 * 1024 * 1024
    if request.headers.get('content-length', '').isdigit() and int(request.headers['content-length']) > limit:
        raise HTTPException(413, 'Image must be smaller than 25 MB.')
    with tempfile.TemporaryDirectory(prefix='tutor-image-upload-') as directory:
        image = Path(directory) / Path(filename).name
        size = 0
        with image.open('wb') as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, 'Image must be smaller than 25 MB.')
                output.write(chunk)
        if not size:
            raise HTTPException(400, 'The image is empty.')

        def recognize():
            result = LocalOCR().extract(image)
            if not result.text.strip():
                raise OCRError('No readable text found. Try a clearer image with text.')
            _, entry = service._repository.session_memory.add_image(
                image, result, user_id=user_id, chat_id=chat_id)
            return {'id': entry['id'], 'filename': entry['image']['original_filename'],
                    'ocr_text': result.text, 'elapsed_ms': result.elapsed_ms}
        try:
            return await run_in_threadpool(recognize)
        except OCRError as error:
            raise HTTPException(422, str(error)) from error
        except LookupError as error:
            raise HTTPException(404, 'Chat expired while the image was being read. Start a new chat.') from error


@router.get('/{chat_id}/images/{image_id}')
def read_image(chat_id: str, image_id: str, service: ChatServiceDependency, user_id: UserIdHeader):
    service.get_chat(chat_id, user_id)
    try:
        entry, image = service._repository.session_memory.get_image(user_id, chat_id, image_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    return FileResponse(image, media_type=entry['image']['media_type'],
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.patch('/{chat_id}/messages/{message_id}',response_model=Message)
def update_message(chat_id:str,message_id:str,payload:MessageUpdateRequest,service:ChatServiceDependency,user_id:UserIdHeader):
    service.get_chat(chat_id,user_id)
    try:service._repository.mutations.edit(chat_id,message_id,user_id,payload.content)
    except LookupError as error:raise HTTPException(404,str(error)) from error
    except ValueError as error:raise HTTPException(400,str(error)) from error
    return next(m for m in service._repository.list_messages(chat_id,user_id) if m.id==message_id)


@router.delete('/{chat_id}/messages/{message_id}')
def delete_message(chat_id:str,message_id:str,service:ChatServiceDependency,user_id:UserIdHeader):
    service.get_chat(chat_id,user_id)
    try:return service._repository.mutations.delete(chat_id,message_id,user_id)
    except LookupError as error:raise HTTPException(404,str(error)) from error


@router.post('/{chat_id}/forget')
def forget_memory(chat_id:str,payload:ForgetRequest,service:ChatServiceDependency,user_id:UserIdHeader):
    service.get_chat(chat_id,user_id)
    return service._repository.mutations.forget(user_id,chat_id,payload.target)


@router.delete('/{chat_id}')
def delete_chat(chat_id:str,service:ChatServiceDependency,user_id:UserIdHeader):
    service.get_chat(chat_id,user_id)
    mutations=service._repository.mutations
    with service._repository.session_memory.transaction():
        ids=[m.id for m in mutations._messages(user_id) if m.chat_id==chat_id]
        plan=mutations._plan(user_id,ids,delete_chats=[chat_id])
        # Also include unattached uploads belonging to this conversation.
        path=service._repository.session_memory._path(user_id,chat_id)
        if path.exists():
            import json
            plan['image_ids']=list(set(plan['image_ids'])|{i['id'] for i in json.loads(path.read_text())['images']})
        return mutations.submit(plan)
