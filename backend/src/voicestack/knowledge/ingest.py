"""Document ingestion for knowledge bases.

collections mode (default): upload with xAI's Files API -> attach to an xAI Collection -> xAI chunks
                   and embeds it; the voice model searches it server-side with file_search.
local mode:        load -> split (LangChain RecursiveCharacterTextSplitter) -> embed (FastEmbed)
                   -> SqlVectorStore; exposed to the model as the search_knowledge function tool.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from pathlib import Path

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from voicestack.config import get_settings
from voicestack.credentials import resolve_server_key
from voicestack.db.models import Document, KnowledgeBase
from voicestack.db.session import session_scope
from voicestack.knowledge.embeddings import get_embeddings
from voicestack.knowledge.vectorstore import SqlVectorStore
from voicestack.xai.client import XAIClient, document_state

log = logging.getLogger(__name__)
SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt", ".html", ".htm", ".csv", ".json"}


def upload_path(doc_id: str, filename: str) -> Path:
    path = get_settings().data_dir / "uploads" / doc_id / Path(filename).name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_documents(path: Path) -> list[LCDocument]:
    suffix = path.suffix.lower()
    source = {"source": path.name}
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            LCDocument(page_content=page.extract_text() or "", metadata={**source, "page": i + 1})
            for i, page in enumerate(reader.pages)
        ]
    if suffix == ".docx":
        import docx2txt

        return [LCDocument(page_content=docx2txt.process(str(path)), metadata=source)]
    if suffix in (".html", ".htm"):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return [LCDocument(page_content=soup.get_text("\n", strip=True), metadata=source)]
    if suffix == ".csv":
        text = path.read_text(encoding="utf-8", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text)))
        return [
            LCDocument(page_content="\n".join(f"{k}: {v}" for k, v in row.items()), metadata={**source, "row": i + 1})
            for i, row in enumerate(rows)
        ]
    return [LCDocument(page_content=path.read_text(encoding="utf-8", errors="replace"), metadata=source)]


async def ingest_document(doc_id: str) -> None:
    async with session_scope() as db:
        doc = await db.get(Document, doc_id)
        kb = await db.get(KnowledgeBase, doc.kb_id) if doc else None
        if not doc or not kb:
            return
        doc.status = "indexing"
        mode, kb_id, collection_id = kb.mode, kb.id, kb.collection_id
        kb_name, kb_description = kb.name, kb.description
        filename, mime = doc.filename, doc.mime
    path = upload_path(doc_id, filename)
    try:
        if mode == "collections":
            chunk_count, file_id = await _ingest_collections(
                path, filename, mime, kb_id, collection_id, kb_name, kb_description, doc_id
            )
            if chunk_count is None:  # xAI is still processing; the knowledge API re-checks it later
                return
        else:
            chunk_count, file_id = await _ingest_local(path, kb_id, doc_id), None
        async with session_scope() as db:
            doc = await db.get(Document, doc_id)
            doc.status, doc.chunk_count, doc.external_file_id, doc.error = "ready", chunk_count, file_id, ""
    except Exception as exc:
        log.exception("Ingestion failed for %s", filename)
        async with session_scope() as db:
            doc = await db.get(Document, doc_id)
            doc.status, doc.error = "error", str(exc)[:1000]


async def _ingest_local(path: Path, kb_id: str, doc_id: str) -> int:
    docs = [d for d in load_documents(path) if d.page_content.strip()]
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)
    if not chunks:
        raise ValueError("No text could be extracted from this file")
    store = SqlVectorStore(get_embeddings(), [kb_id])
    await store.aadd_texts(
        [c.page_content for c in chunks],
        metadatas=[{**c.metadata, "kb_id": kb_id, "document_id": doc_id} for c in chunks],
    )
    return len(chunks)


async def ensure_collection(kb_id: str, collection_id: str | None, name: str, description: str, key: str) -> str:
    """Create the xAI Collection for a knowledge base the first time it is needed."""
    if collection_id:
        return collection_id
    async with XAIClient(key) as client:
        created = await client.create_collection(f"voicestack-{name}"[:120], description)
    collection_id = created["collection_id"]
    async with session_scope() as db:
        kb = await db.get(KnowledgeBase, kb_id)
        kb.collection_id = collection_id
    return collection_id


async def _ingest_collections(
    path: Path, filename: str, mime: str, kb_id: str, collection_id: str | None, kb_name: str, kb_description: str, doc_id: str
) -> tuple[int | None, str]:
    async with session_scope() as db:
        key = await resolve_server_key(db)
    if not key:
        raise ValueError("xAI Collections need a server-side xAI API key (Settings or XAI_API_KEY)")
    collection_id = await ensure_collection(kb_id, collection_id, kb_name, kb_description, key.value)
    async with XAIClient(key.value) as client:
        uploaded = await client.upload_file(filename, path.read_bytes(), mime or "application/octet-stream")
        await client.add_document(collection_id, uploaded["id"])
        async with session_scope() as db:
            (await db.get(Document, doc_id)).external_file_id = uploaded["id"]
        # xAI chunks and embeds asynchronously; wait so the document only shows "ready" when searchable.
        for _ in range(120):
            docs = await client.list_documents(collection_id)
            doc = next((d for d in docs if (d.get("file_metadata") or {}).get("file_id") == uploaded["id"]), None)
            state = document_state(doc) if doc else "processing"
            if state == "processed":
                return int(doc.get("chunk_count") or 0), uploaded["id"]
            if state == "failed":
                raise ValueError(doc.get("error_message") or "xAI could not process this file")
            await asyncio.sleep(3)
    log.warning("xAI is still processing %s after 6 minutes; leaving it as indexing", filename)
    return None, uploaded["id"]


_last_refresh: dict[str, float] = {}


async def refresh_collection_status(kb: KnowledgeBase, docs: list[Document]) -> None:
    """Re-check documents xAI is still processing (throttled to once per 10 s per knowledge base)."""
    import time

    pending = [d for d in docs if d.status == "indexing" and d.external_file_id]
    if kb.mode != "collections" or not kb.collection_id or not pending:
        return
    if time.monotonic() - _last_refresh.get(kb.id, 0) < 10:
        return
    _last_refresh[kb.id] = time.monotonic()
    async with session_scope() as db:
        key = await resolve_server_key(db)
    if not key:
        return
    async with XAIClient(key.value) as client:
        remote = {(d.get("file_metadata") or {}).get("file_id"): d for d in await client.list_documents(kb.collection_id)}
    async with session_scope() as db:
        for doc in pending:
            info = remote.get(doc.external_file_id)
            if not info:
                continue
            state = document_state(info)
            row = await db.get(Document, doc.id)
            if state == "processed":
                row.status, row.chunk_count = "ready", int(info.get("chunk_count") or 0)
            elif state == "failed":
                row.status, row.error = "error", info.get("error_message") or "xAI could not process this file"


async def search_local(kb_ids: list[str], query: str, k: int = 4) -> list[dict]:
    store = SqlVectorStore(get_embeddings(), kb_ids)
    results = await store.asimilarity_search_with_score(query, k=k)
    return [
        {"text": d.page_content, "source": d.metadata.get("source"), "page": d.metadata.get("page"), "score": round(s, 4)}
        for d, s in results
    ]
