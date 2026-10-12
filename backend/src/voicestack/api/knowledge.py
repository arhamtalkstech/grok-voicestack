from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import get_or_404, slugify, to_dict
from voicestack.credentials import resolve_server_key
from voicestack.db.models import Document, KnowledgeBase
from voicestack.db.session import get_db
from voicestack.knowledge.ingest import SUPPORTED, ingest_document, refresh_collection_status, search_local, upload_path
from voicestack.knowledge.vectorstore import delete_document_chunks
from voicestack.xai.client import XAIClient

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
MAX_UPLOAD = 50 * 1024 * 1024


class KbIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    mode: Literal["local", "collections"] = "collections"
    collection_id: str | None = None
    top_k: int = Field(4, ge=1, le=20)


async def _kb_payload(db: AsyncSession, kb: KnowledgeBase) -> dict[str, Any]:
    docs = (
        (await db.execute(select(Document).where(Document.kb_id == kb.id).order_by(Document.created_at.desc()))).scalars().all()
    )
    try:
        await refresh_collection_status(kb, list(docs))
        for doc in docs:
            await db.refresh(doc)
    except Exception:  # status refresh is best-effort; the list still renders
        pass
    return {**to_dict(kb), "documents": [to_dict(d) for d in docs]}


@router.get("")
async def list_kbs(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    kbs = (await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at))).scalars().all()
    return [await _kb_payload(db, kb) for kb in kbs]


@router.post("", status_code=201)
async def create_kb(body: KbIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    slug, n = slugify(body.name), 2
    while (await db.execute(select(KnowledgeBase).where(KnowledgeBase.slug == slug))).scalar_one_or_none():
        slug, n = f"{slugify(body.name)}-{n}", n + 1
    collection_id = body.collection_id
    if body.mode == "collections" and not collection_id:
        key = await resolve_server_key(db)
        if not key:
            raise HTTPException(412, "xAI Collections need a server-side xAI API key (Settings or XAI_API_KEY)")
        async with XAIClient(key.value) as client:
            created = await client.create_collection(f"voicestack-{body.name}"[:120], body.description)
        collection_id = created["collection_id"]
    kb = KnowledgeBase(
        name=body.name, slug=slug, description=body.description, mode=body.mode, collection_id=collection_id, top_k=body.top_k
    )
    db.add(kb)
    await db.flush()
    return await _kb_payload(db, kb)


@router.get("/{kb_id}")
async def get_kb(kb_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await _kb_payload(db, await get_or_404(db, KnowledgeBase, kb_id))


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(kb_id: str, db: AsyncSession = Depends(get_db), delete_collection: bool = True) -> None:
    kb = await get_or_404(db, KnowledgeBase, kb_id)
    if kb.mode == "collections" and kb.collection_id and delete_collection:
        key = await resolve_server_key(db)
        if key:
            async with XAIClient(key.value) as client:
                try:
                    await client.delete_collection(kb.collection_id)
                except Exception as exc:  # already gone, or created by someone else's key
                    if "404" not in str(exc):
                        raise HTTPException(502, f"xAI could not delete the collection: {exc}") from exc
    await db.delete(kb)


@router.post("/{kb_id}/documents", status_code=202)
async def upload(
    kb_id: str, background: BackgroundTasks, files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    await get_or_404(db, KnowledgeBase, kb_id)
    created = []
    for f in files:
        name = Path(f.filename or "upload").name
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, f"{name}: supported types are {', '.join(sorted(SUPPORTED))}")
        content = await f.read()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, f"{name} is larger than 50 MB")
        doc = Document(kb_id=kb_id, filename=name, mime=f.content_type or "", size=len(content))
        db.add(doc)
        await db.flush()
        upload_path(doc.id, name).write_bytes(content)
        created.append(doc)
    await db.commit()
    for doc in created:
        background.add_task(ingest_document, doc.id)
    return [to_dict(d) for d in created]


@router.delete("/{kb_id}/documents/{doc_id}", status_code=204)
async def delete_document(kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db)) -> None:
    doc = await get_or_404(db, Document, doc_id)
    if doc.kb_id != kb_id:
        raise HTTPException(404, "Document not found in this knowledge base")
    kb = await get_or_404(db, KnowledgeBase, kb_id)
    if kb.mode == "collections" and kb.collection_id and doc.external_file_id:
        key = await resolve_server_key(db)
        if key:
            async with XAIClient(key.value) as client:
                try:
                    await client.delete_document(kb.collection_id, doc.external_file_id)
                except Exception as exc:
                    if "404" not in str(exc):
                        raise HTTPException(502, f"xAI could not remove the document: {exc}") from exc
    await delete_document_chunks(doc_id)
    await db.delete(doc)


def chunk_text(content: str | None) -> str:
    """Collections return chunk content as a JSON list of {page_number, text}; show the text."""
    if not content:
        return ""
    try:
        pages = json.loads(content)
        return "\n".join(p.get("text", "") for p in pages if isinstance(p, dict)) or content
    except (ValueError, TypeError, AttributeError):
        return content


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(4, ge=1, le=20)


@router.post("/{kb_id}/search")
async def search(kb_id: str, body: SearchIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    kb = await get_or_404(db, KnowledgeBase, kb_id)
    if kb.mode == "collections":
        if not kb.collection_id:
            return {"results": [], "note": "No documents yet"}
        key = await resolve_server_key(db)
        if not key:
            raise HTTPException(412, "Collection search needs a server-side xAI API key")
        async with XAIClient(key.value) as client:
            matches = await client.search_documents(body.query, [kb.collection_id], limit=body.k)
        return {
            "results": [
                {
                    "text": chunk_text(m.get("chunk_content")),
                    "source": (m.get("fields") or {}).get("title") or m.get("file_id"),
                    "page": m.get("page_number"),
                    "score": round(m.get("score") or 0, 4),
                }
                for m in matches
            ]
        }
    count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.kb_id == kb_id, Document.status == "ready"))
    ).scalar()
    if not count:
        return {"results": [], "note": "No indexed documents yet"}
    return {"results": await search_local([kb_id], body.query, k=body.k)}
