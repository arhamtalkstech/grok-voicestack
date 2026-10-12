<!-- Source: https://docs.x.ai/developers/files/collections/api (markdown: https://docs.x.ai/developers/files/collections/api.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Files & Collections

# Using Collections via API

This guide walks you through managing collections programmatically using the xAI SDK and REST API.

## Creating a Management Key

To use the Collections API, you need to create a Management API Key with the `AddFileToCollection` permission. This permission is required for uploading documents to collections.

1. Navigate to the **Management Keys** section in the [xAI Console](https://console.x.ai/team/default/settings/management-keys?utm_source=docs\&utm_medium=referral\&utm_campaign=developers-files-collections-api\&utm_content=management-keys)
2. Click on **Create Management Key**
3. Select the `AddFileToCollection` permission along with any other permissions you need
4. If you need to perform operations other than uploading documents (such as creating, updating, or deleting collections), enable the corresponding permissions in the **Collections Endpoint** group
5. Copy and securely store your Management API Key

> [!WARNING]
>
> Make sure to copy your Management API Key immediately after creation. You won't be able to see it again.

## Creating a collection

```javascript customLanguage="javascriptWithoutSDK"
const response = await fetch('https://management-api.x.ai/v1/collections', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}`,
  },
  body: JSON.stringify({ collection_name: 'SEC Filings' }),
});

const collection = await response.json();
console.log(collection);
```

```bash
curl https://management-api.x.ai/v1/collections \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY" \
  -d '{"collection_name": "SEC Filings"}'
```

```python customLanguage="pythonXAI"
import os
from xai_sdk import Client
client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    management_api_key=os.getenv("XAI_MANAGEMENT_API_KEY"),
    timeout=3600,
)

collection = client.collections.create(
    name="SEC Filings",
)

print(collection)
```

## Listing collections

```javascript customLanguage="javascriptWithoutSDK"
const response = await fetch('https://management-api.x.ai/v1/collections', {
  headers: {
    'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}`,
  },
});

const collections = await response.json();
console.log(collections);
```

```bash
curl https://management-api.x.ai/v1/collections \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY"
```

```python customLanguage="pythonXAI"
# ... Create client
collections = client.collections.list()
print(collections)
```

## Viewing collection configuration

```javascript customLanguage="javascriptWithoutSDK"
const collectionId = 'collection_dbc087b1-6c99-493d-86c6-b401fee34a9d';
const response = await fetch(`https://management-api.x.ai/v1/collections/${collectionId}`, {
  headers: {
    'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}`,
  },
});

const collection = await response.json();
console.log(collection);
```

```bash
curl https://management-api.x.ai/v1/collections/collection_dbc087b1-6c99-493d-86c6-b401fee34a9d \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY"
```

```python customLanguage="pythonXAI"
# ... Create client
collection = client.collections.get("collection_dbc087b1-6c99-493d-86c6-b401fee34a9d")

print(collection)
```

## Updating collection configuration

```javascript customLanguage="javascriptWithoutSDK"
const collectionId = 'collection_dbc087b1-6c99-493d-86c6-b401fee34a9d';
const response = await fetch(`https://management-api.x.ai/v1/collections/${collectionId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}`,
  },
  body: JSON.stringify({ collection_name: 'SEC Filings (New)' }),
});

const collection = await response.json();
console.log(collection);
```

```bash
curl https://management-api.x.ai/v1/collections/collection_dbc087b1-6c99-493d-86c6-b401fee34a9d \
  -X PUT \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY" \
  -d '{"collection_name": "SEC Filings (New)"}'
```

```python customLanguage="pythonXAI"
# ... Create client
collection = client.collections.update(
    "collection_dbc087b1-6c99-493d-86c6-b401fee34a9d",
    name="SEC Filings (New)"
)

print(collection)
```

## Uploading documents

Uploading a document to a collection is a two-step process:

1. Upload the file to the xAI API
2. Add the uploaded file to your collection

```javascript customLanguage="javascriptWithoutSDK"
import fs from 'fs';

const collectionId = 'collection_dbc087b1-6c99-493d-86c6-b401fee34a9d';

// Step 1: Upload file
const fileData = fs.readFileSync('tesla-20241231.html');
const formData = new FormData();
formData.append('file', new Blob([fileData], { type: 'text/html' }), 'tesla-20241231.html');
formData.append('purpose', 'assistants');
const uploadResponse = await fetch('https://api.x.ai/v1/files', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${process.env.XAI_API_KEY}` },
  body: formData,
});

const { id: fileId } = await uploadResponse.json();

// Step 2: Add to collection
await fetch(`https://management-api.x.ai/v1/collections/${collectionId}/documents/${fileId}`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}` },
});

```

```bash
# Step 1: Upload file
curl https://api.x.ai/v1/files \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -F file=@tesla-20241231.html

# Step 2: Add file to collection (use file_id from step 1)
curl -X POST https://management-api.x.ai/v1/collections/$COLLECTION_ID/documents/$FILE_ID \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY"
```

```python customLanguage="pythonXAI"
# ... Create client
with open("tesla-20241231.html", "rb") as file:
    file_data = file.read()

document = client.collections.upload_document(
    collection_id="collection_dbc087b1-6c99-493d-86c6-b401fee34a9d",
    name="tesla-20241231.html",
    data=file_data,
)
print(document)
```

### Uploading with metadata fields

If your collection has [metadata fields](https://docs.x.ai/developers/files/collections/metadata) defined (the collection must have these fields set in `field_definitions` when created or updated - see the linked metadata page for details), include them using the `fields` parameter:

```bash
curl https://management-api.x.ai/v1/collections/collection_dbc087b1-6c99-493d-86c6-b401fee34a9d/documents \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY" \
  -F "name=paper.pdf" \
  -F "data=@paper.pdf" \
  -F "content_type=application/pdf" \
  -F 'fields={"author": "Sandra Kim", "year": "2024", "title": "Q3 Revenue Analysis"}'
```

```python customLanguage="pythonXAI"
# ... Create client
with open("paper.pdf", "rb") as file:
    file_data = file.read()

document = client.collections.upload_document(
    collection_id="collection_dbc087b1-6c99-493d-86c6-b401fee34a9d",
    name="paper.pdf",
    data=file_data,
    fields={
        "author": "Sandra Kim",
        "year": "2024",
        "title": "Q3 Revenue Analysis"
    },
)
print(document)
```

## Searching documents

You can also search documents using the Responses API with the `file_search` tool. See the [Collections Search Tool](https://docs.x.ai/developers/tools/collections-search) guide for more details.

```javascript customLanguage="javascriptWithoutSDK"
const response = await fetch('https://api.x.ai/v1/documents/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${process.env.XAI_API_KEY}`,
  },
  body: JSON.stringify({
    query: 'What were the key revenue drivers based on the SEC filings?',
    source: {
      collection_ids: ['collection_dbc087b1-6c99-493d-86c6-b401fee34a9d'],
    },
  }),
});

const results = await response.json();
console.log(results);
```

```bash
curl https://api.x.ai/v1/documents/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
    "query": "What were the key revenue drivers based on the SEC filings?",
    "source": {
      "collection_ids": ["collection_dbc087b1-6c99-493d-86c6-b401fee34a9d"]
    }
  }'
```

```python customLanguage="pythonXAI"
# ... Create client
response = client.collections.search(
    query="What were the key revenue drivers based on the SEC filings?",
    collection_ids=["collection_dbc087b1-6c99-493d-86c6-b401fee34a9d"],
)
print(response)
```

### Search modes

There are three search methods available:

* **Keyword search**
* **Semantic search**
* **Hybrid search** (combines both keyword and semantic methods)

By default, the system uses hybrid search, which generally delivers the best and most comprehensive results.

| Mode | Description | Best for | Drawbacks |
|------|-------------|----------|-----------|
| Keyword | Searches for exact matches of specified words, phrases, or numbers | Precise terms (e.g., account numbers, dates, specific financial figures) | May miss contextually relevant content |
| Semantic | Understands meaning and context to find conceptually related content | Discovering general ideas, topics, or intent even when exact words differ | Less precise for specific terms |
| Hybrid | Combines keyword and semantic search for broader and more accurate results | Most real-world use cases | Slightly higher latency |

The hybrid approach balances precision and recall, making it the recommended default for the majority of queries.

An example to set hybrid mode:

```bash
curl https://api.x.ai/v1/documents/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
      "query": "What were the key revenue drivers based on the SEC filings?",
      "source": {
          "collection_ids": [
              "collection_dbc087b1-6c99-493d-86c6-b401fee34a9d"
          ]
      },
      "retrieval_mode": {"type": "hybrid"}
}'
```

You can set `"retrieval_mode": {"type": "keyword"}` for keyword search and `"retrieval_mode": {"type": "semantic"}` for semantic search.

## Deleting a document

```javascript customLanguage="javascriptWithoutSDK"
const collectionId = 'collection_dbc087b1-6c99-493d-86c6-b401fee34a9d';
const fileId = 'file_55a709d4-8edc-4f83-84d9-9f04fe49f832';

await fetch(`https://management-api.x.ai/v1/collections/${collectionId}/documents/${fileId}`, {
  method: 'DELETE',
  headers: { 'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}` },
});

```

```bash
curl https://management-api.x.ai/v1/collections/collection_dbc087b1-6c99-493d-86c6-b401fee34a9d/documents/file_55a709d4-8edc-4f83-84d9-9f04fe49f832 \
  -X DELETE \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY"
```

```python customLanguage="pythonXAI"
# ... Create client

client.collections.remove_document(
    collection_id="collection_dbc087b1-6c99-493d-86c6-b401fee34a9d",
    file_id="file_55a709d4-8edc-4f83-84d9-9f04fe49f832",
)
```

## Deleting a collection

```javascript customLanguage="javascriptWithoutSDK"
const collectionId = 'collection_dbc087b1-6c99-493d-86c6-b401fee34a9d';

await fetch(`https://management-api.x.ai/v1/collections/${collectionId}`, {
  method: 'DELETE',
  headers: { 'Authorization': `Bearer ${process.env.XAI_MANAGEMENT_API_KEY}` },
});

```

```bash
curl https://management-api.x.ai/v1/collections/collection_dbc087b1-6c99-493d-86c6-b401fee34a9d \
  -X DELETE \
  -H "Authorization: Bearer $XAI_MANAGEMENT_API_KEY"
```

```python customLanguage="pythonXAI"
# ... Create client

client.collections.delete(collection_id="collection_dbc087b1-6c99-493d-86c6-b401fee34a9d")
```

## Next Steps
