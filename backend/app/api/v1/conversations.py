"""Conversation + streaming chat endpoints.

The chat endpoint hands the user message to the LangGraph orchestrator and
streams back an SSE event feed. Full flow in docs/20-code-flow.md.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace
from app.core.errors import NotFoundError
from app.db.models import Conversation, Message, MessageRole, User, Workspace
from app.db.session import get_db
from app.schemas.user import ConversationOut, MessageOut

router = APIRouter()


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conv = Conversation(workspace_id=workspace.id, created_by=user.id, title="New research", thread_id=str(uuid.uuid4()))
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: str,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace.id:
        raise NotFoundError("conversation", conversation_id)
    return conv


@router.post("/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: str,
    content: str,
    workspace: Workspace = Depends(get_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    import json

    from app.orchestrator.service import run_conversation_stream

    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace.id:
        raise NotFoundError("conversation", conversation_id)

    db.add(Message(conversation_id=conv.id, role=MessageRole.USER, content=content))
    db.commit()

    user_message = {"role": "user", "content": content, "id": str(uuid.uuid4())}

    async def event_stream():
        async for event in run_conversation_stream(conv.thread_id, user_message, workspace.id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: str,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace.id:
        raise NotFoundError("conversation", conversation_id)
    return sorted(conv.messages, key=lambda m: m.created_at)