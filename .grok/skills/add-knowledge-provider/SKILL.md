---
name: add-knowledge-provider
description: Give Voice Stack agents documents to answer from, using the built-in knowledge bases, xAI Collections, or the user's own retriever. Use when asked to add RAG, documents, a vector store, or search over company data.
---

# Add knowledge

Modes and the pipeline are in `docs/knowledge.md`.

1. If the user has files, create a knowledge base (`POST /api/knowledge`, default `collections` mode: xAI Files API + Collection, regular API key). Upload with `POST /api/knowledge/{id}/documents` and wait until every document is `ready`. Use `mode: local` only if files must stay on the server.
2. If they already have an xAI Collection, pass its `collection_id` when creating the knowledge base.
3. If they have their own search system (Elasticsearch, pgvector, Confluence…), write a code plugin that wraps it as a LangChain tool. See "Use your retriever for knowledge" in `docs/extending.md`.
4. Verify retrieval with real questions: `POST /api/knowledge/{id}/search`. Show the user the top passages.
5. Attach the knowledge base or tool to the agent, then confirm in a preview call that the agent answers from it and says it does not know when nothing matches.
