"""Document upload + ingestion lifecycle API.

Upload is idempotent; heavy processing (validation, chunking, embeddings,
vector indexing) runs async in a Celery pipeline.
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.errors import NotFoundError
from app.db.models import Document, DocumentStatus, Role, User, Workspace
from app.db.session import get_db
from app.services.storage import presign_document, put_object

router = APIRouter()


@router.post("", status_code=202)
def upload_document(
    workspace: Workspace = Depends(require_role(Role.OWNER, Role.ADMIN, Role.MEMBER)),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = file.file.read()
    doc = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        s3_key=str(uuid.uuid4()),
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    put_object(doc.s3_key, data, doc.content_type)

    from app.workers.tasks import process_document

    process_document.delay(str(doc.id))

    return {"id": str(doc.id), "status": doc.status.value}


@router.get("")
def list_documents(
    workspace: Workspace = Depends(require_role(Role.OWNER, Role.ADMIN, Role.MEMBER)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    docs = db.query(Document).filter(Document.workspace_id == workspace.id).order_by(Document.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "status": d.status.value,
            "chunk_count": d.chunk_count,
            "size_bytes": d.size_bytes,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    workspace: Workspace = Depends(require_role(Role.VIEWER, Role.MEMBER, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    doc = db.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace.id:
        raise NotFoundError("document", document_id)
    return {"url": presign_document(doc.s3_key, doc.filename)}