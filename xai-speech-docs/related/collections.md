<!-- Source: https://docs.x.ai/developers/files/collections (markdown: https://docs.x.ai/developers/files/collections.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Files & Collections

# Collections

Collections offers xAI API users a robust set of tools and methods to seamlessly integrate their enterprise requirements and internal knowledge bases with the xAI API. Whether you're building a RAG application or need to search across large document sets, Collections provides the infrastructure to manage and query your content.

> [!NOTE]
>
> **Looking for Files?** If you want to attach files directly to chat messages for conversation context, see [Files](https://docs.x.ai/developers/files). Collections are different—they provide persistent document storage with semantic search across many documents.

## Core Concepts

There are two entities that users can create within the Collections service:

* **File** — A single entity of a user-uploaded file.
* **Collection** — A group of files linked together, with an embedding index for efficient retrieval.
  * When you create a collection you have the option to automatically generate embeddings for any files uploaded to that collection. You can then perform semantic search across files in multiple collections.
  * A single file can belong to multiple collections.

## What You Can Do

With Collections, you can:

* **Create collections** to organize your documents
* **Upload documents** in various formats (HTML, PDF, text, etc.)
* **Search semantically** across your documents using natural language queries
* **Configure chunking and embeddings** to optimize retrieval
* **Manage documents** by listing, updating, and deleting them

## Getting Started

Choose how you want to work with Collections:

* [Using the Console →](https://docs.x.ai/console/collections) - Create collections and upload documents through the xAI Console interface
* [Using the API →](https://docs.x.ai/developers/files/collections/api) - Programmatically manage collections with the SDK and REST API

## Metadata Fields

Collections support **metadata fields** — structured attributes you can attach to documents for enhanced retrieval and data integrity:

* **Filtered retrieval** — Narrow search results to documents matching specific criteria (e.g., `author="Sandra Kim"`)
* **Contextual embeddings** — Inject metadata into chunks to improve retrieval accuracy (e.g., prepending document title to each chunk)
* **Data integrity constraints** — Enforce required fields or uniqueness across documents

When creating a collection, define metadata fields with options like `required`, `unique`, and `inject_into_chunk` to control how metadata is validated and used during search.

[Learn more about metadata fields →](https://docs.x.ai/developers/files/collections/metadata)

## Usage Limits

To be able to upload files and add to a collection you must have credits in your account.

**Maximum file size**: 100MB

Please [contact us](https://x.ai/contact) to increase any of these limits.

## Data Privacy

We do not use user data stored on Collections for model training purposes.

## Supported MIME Types

While we support any `UTF-8` encoded text file, we also have special file conversion and chunking techniques for certain MIME types.

The following would be a non-exhaustive list for the MIME types that we support:

* application/csv
* application/dart
* application/ecmascript
* application/epub
* application/epub+zip
* application/json
* application/ms-java
* application/msword
* application/pdf
* application/typescript
* application/vnd.adobe.pdf
* application/vnd.curl
* application/vnd.dart
* application/vnd.jupyter
* application/vnd.ms-excel
* application/vnd.ms-outlook
* application/vnd.oasis.opendocument.text
* application/vnd.openxmlformats-officedocument.presentationml.presentation
* application/vnd.openxmlformats-officedocument.presentationml.slide
* application/vnd.openxmlformats-officedocument.presentationml.slideshow
* application/vnd.openxmlformats-officedocument.presentationml.template
* application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
* application/vnd.openxmlformats-officedocument.spreadsheetml.template
* application/vnd.openxmlformats-officedocument.wordprocessingml.document
* application/x-csh
* application/x-epub+zip
* application/x-hwp
* application/x-hwp-v5
* application/x-latex
* application/x-pdf
* application/x-php
* application/x-powershell
* application/x-sh
* application/x-shellscript
* application/x-tex
* application/x-zsh
* application/xhtml
* application/xml
* application/zip
* text/cache-manifest
* text/calendar
* text/css
* text/csv
* text/html
* text/javascript
* text/jsx
* text/markdown
* text/n3
* text/php
* text/plain
* text/rtf
* text/tab-separated-values
* text/troff
* text/tsv
* text/tsx
* text/turtle
* text/uri-list
* text/vcard
* text/vtt
* text/x-asm
* text/x-bibtex
* text/x-c
* text/x-c++hdr
* text/x-c++src
* text/x-chdr
* text/x-coffeescript
* text/x-csh
* text/x-csharp
* text/x-csrc
* text/x-d
* text/x-diff
* text/x-emacs-lisp
* text/x-erlang
* text/x-go
* text/x-haskell
* text/x-java
* text/x-java-properties
* text/x-java-source
* text/x-kotlin
* text/x-lisp
* text/x-lua
* text/x-objcsrc
* text/x-pascal
* text/x-perl
* text/x-perl-script
* text/x-python
* text/x-python-script
* text/x-r-markdown
* text/x-rst
* text/x-ruby-script
* text/x-rust
* text/x-sass
* text/x-scala
* text/x-scheme
* text/x-script.python
* text/x-scss
* text/x-sh
* text/x-sql
* text/x-swift
* text/x-tcl
* text/x-tex
* text/x-vbasic
* text/x-vcalendar
* text/xml
* text/xml-dtd
* text/yaml
