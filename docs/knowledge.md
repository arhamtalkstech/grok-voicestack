# Knowledge (RAG)

A knowledge base is a set of documents an agent answers from during calls. It runs in one of two modes, chosen when you create it.

## xAI Collections (default)

The files live in xAI, and the voice model searches them server-side, with no function round trip. Every call below uses your regular xAI API key on `api.x.ai`, so you do not need a Management API key. This was verified live on 2026-10-12: create, upload, attach, index, search, and delete all succeeded with a regular key. xAI's Collections guide describes the management calls (create, attach, delete) on `management-api.x.ai` with a Management API key. That host rejects a regular key, so Voice Stack uses the `api.x.ai` routes.

Indexing time at xAI varies from seconds to several minutes. The upload waits up to six minutes and then shows the document as "indexing". The Knowledge page re-checks it until xAI finishes.

| Step | Call |
|---|---|
| Create the collection (on knowledge-base creation, or on first upload) | `POST /v1/collections` `{"collection_name", "field_definitions": []}` |
| Upload a file | `POST /v1/files` (Files API, multipart) |
| Attach it to the collection | `POST /v1/collections/{collection_id}/documents/{file_id}` `{"collection_id", "file_id", "fields": {}}` |
| Wait until searchable | `GET /v1/collections/{collection_id}/documents` until `status` is processed (2). Chunk count comes from `chunk_count`. |
| Search in a call | `session.tools` gets `{"type": "file_search", "vector_store_ids": [collection_id], "max_num_results": top_k}`. xAI runs it (it appears as a `collections_search` call). |
| Try a search (UI) | `POST /v1/documents/search` |
| Remove a document | `DELETE /v1/collections/{collection_id}/documents/{file_id}` (this also deletes the file) |
| Delete the knowledge base | `DELETE /v1/collections/{collection_id}` |

xAI chunks and embeds the files itself (`grok-embedding-small`, about 4 KB chunks). Voice Stack keeps a copy of each upload in `DATA_DIR/uploads`, and a row per document with its xAI `file_id`, status, and chunk count.

The compiler adds a Conversation Flow line telling the agent to search the knowledge base before saying it does not know, and to answer only from the results. The `collections_search` call is stored on the conversation as a server-side tool turn.

## Local

Choose **In Voice Stack** when files must not leave your server. The pipeline is all LangChain and needs no key:

1. **Load.** PDF (`pypdf`, per page), DOCX (`docx2txt`), HTML (BeautifulSoup), CSV (per row), Markdown, text, and JSON.
2. **Split.** `RecursiveCharacterTextSplitter`, 1,000 characters with 150 overlap.
3. **Embed.** FastEmbed (`BAAI/bge-small-en-v1.5`) runs locally on CPU. It downloads into `DATA_DIR/models` on first use (or build with `--build-arg PRELOAD_EMBEDDINGS=true`). Set `EMBEDDINGS_PROVIDER=openai_compatible` for a hosted embeddings API.
4. **Store.** `SqlVectorStore` is a LangChain `VectorStore` over the `chunks` table, using brute-force cosine search on SQLite or Postgres.

A local knowledge base gives the agent a `search_knowledge(query)` function tool, run by Voice Stack. Results include source, page, and score.

## Bringing your own retriever

Wrap any search system (Elasticsearch, pgvector, Confluence) as a LangChain tool in a code plugin and attach it to the agent. See [extending.md](extending.md).
