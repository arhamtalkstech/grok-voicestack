"""A LangChain VectorStore over the `chunks` table.

Works on SQLite and Postgres with no extensions, using brute-force cosine similarity per knowledge
base. That is fast enough for tens of thousands of chunks. For larger corpora, swap in
langchain-postgres PGVector (or any LangChain VectorStore) through a KnowledgeProvider.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from sqlalchemy import delete, select

from voicestack.db.models import Chunk
from voicestack.db.session import session_scope


class SqlVectorStore(VectorStore):
    def __init__(self, embeddings: Embeddings, kb_ids: list[str]):
        self._embeddings = embeddings
        self.kb_ids = kb_ids

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    async def aadd_texts(
        self, texts: Iterable[str], metadatas: list[dict] | None = None, *, ids: list[str] | None = None, **kwargs: Any
    ) -> list[str]:
        texts = list(texts)
        if not texts:
            return []
        metadatas = metadatas or [{} for _ in texts]
        vectors = await self._embeddings.aembed_documents(texts)
        rows = []
        async with session_scope() as db:
            for i, (text, meta, vec) in enumerate(zip(texts, metadatas, vectors, strict=True)):
                arr = np.asarray(vec, dtype=np.float32)
                arr /= np.linalg.norm(arr) or 1.0
                row = Chunk(
                    kb_id=meta["kb_id"],
                    document_id=meta["document_id"],
                    text=text,
                    meta=meta,
                    embedding=arr.tobytes(),
                    dim=arr.shape[0],
                )
                if ids:
                    row.id = ids[i]
                db.add(row)
                rows.append(row)
        return [r.id for r in rows]

    async def asimilarity_search_with_score(self, query: str, k: int = 4, **kwargs: Any) -> list[tuple[Document, float]]:
        qvec = np.asarray(await self._embeddings.aembed_query(query), dtype=np.float32)
        qvec /= np.linalg.norm(qvec) or 1.0
        async with session_scope() as db:
            rows = (await db.execute(select(Chunk).where(Chunk.kb_id.in_(self.kb_ids)))).scalars().all()
        if not rows:
            return []
        matrix = np.stack([np.frombuffer(r.embedding, dtype=np.float32) for r in rows if r.dim == qvec.shape[0]])
        valid = [r for r in rows if r.dim == qvec.shape[0]]
        scores = matrix @ qvec
        top = np.argsort(-scores)[:k]
        return [(Document(page_content=valid[i].text, metadata=valid[i].meta), float(scores[i])) for i in top]

    async def asimilarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        return [d for d, _ in await self.asimilarity_search_with_score(query, k, **kwargs)]

    # Sync API: Voice Stack is async end to end.
    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        raise NotImplementedError("Use asimilarity_search")

    @classmethod
    def from_texts(cls, texts: list[str], embedding: Embeddings, metadatas: list[dict] | None = None, **kwargs: Any):
        raise NotImplementedError("Create SqlVectorStore(embeddings, kb_ids) and call aadd_texts")


async def delete_document_chunks(document_id: str) -> None:
    async with session_scope() as db:
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
