"""Embedding providers behind LangChain's Embeddings interface.

Default: FastEmbed (local ONNX, no API key). Any OpenAI-compatible embeddings endpoint can replace
it via EMBEDDINGS_PROVIDER=openai_compatible. To plug in another provider, return a different
langchain_core.embeddings.Embeddings from get_embeddings().
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from voicestack.config import get_settings


class FastEmbedLocal(Embeddings):
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding  # imported lazily: the model downloads on first use

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(get_settings().data_dir / "models"))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed([text]))).tolist()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


@lru_cache
def get_embeddings() -> Embeddings:
    settings = get_settings()
    if settings.embeddings_provider == "openai_compatible":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.embeddings_model,
            base_url=settings.embeddings_api_base,
            api_key=settings.embeddings_api_key,
        )
    return FastEmbedLocal(settings.embeddings_model)
