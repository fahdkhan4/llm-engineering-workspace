# Text Extractor

Upload PDF and Word documents, extract everything out of them into SQLite, then
ask questions about them from a chat frontend.

## Run

```bash
uv sync
uv run fastapi dev main.py      # http://127.0.0.1:8000  (docs at /docs)
```

Tables and the search index are created on startup. Nothing else to set up.

## Endpoints

| Method | Path                     | What it does                                        |
| ------ | ------------------------ | --------------------------------------------------- |
| POST   | `/`                      | Upload a PDF/.docx, extract it, store it             |
| GET    | `/`                      | Ask a question, answered from the stored documents   |
| GET    | `/documents`             | List uploaded documents                              |
| GET    | `/documents/{id}`        | One document with its metadata                       |
| DELETE | `/documents/{id}`        | Delete a document and everything extracted from it   |
| GET    | `/health`                | Health check                                         |

### Upload

```bash
curl -F "file=@report.pdf" http://127.0.0.1:8000/
```

Returns the document row plus how many blocks, tables and chunks were stored.
Uploading the same file twice is free: it is matched by content hash and
`already_processed: true` comes back without re-parsing.

### Ask

```bash
curl "http://127.0.0.1:8000/?question=What was the revenue last quarter"
```

Query parameters: `question` (required), `document_id` (limit to one document),
`session_key` (continue a chat thread), `top_k` (how many chunks to retrieve).

The response carries the `answer`, the `sources` it was based on (document,
section, page range) and the `session_key` to send with the next question.

## How it fits together

```
POST /  ->  controller  ->  document_service
                              |- helper/file_utils      type sniffing + sha256
                              |- helper/pdf_extractor    PyMuPDF + pdfplumber
                              |- helper/docx_extractor   python-docx
                              |- helper/chunker          blocks -> chunks
                              `- repository              write to SQLite

GET  /  ->  controller  ->  qa_service
                              |- repository.search_chunks   hybrid retrieval
                              |    |- FTS5 / BM25             keyword channel
                              |    |- llm/embedder            semantic channel
                              |    `- RRF                     rank fusion
                              |- llm/llm_client             answer + citations
                              `- chat_repository            thread + history
```

### Tables

| Table             | Holds                                                       |
| ----------------- | ----------------------------------------------------------- |
| `documents`       | one row per file: metadata, counts, status, content hash     |
| `document_blocks` | headings, paragraphs, lists, headers/footers in reading order|
| `document_tables` | tables as markdown (for the LLM) and JSON (for the UI)       |
| `document_chunks` | retrieval units, with the section and pages they came from   |
| `chat_sessions`   | one chat thread                                              |
| `chat_messages`   | the turns of a thread, with the chunks each answer used      |

`document_chunks_fts` is an FTS5 index over the chunks, kept in sync by
triggers. `document_chunks.embedding` holds the matching 1024-dim vector.

## Retrieval

`GET /` searches two channels and fuses them:

- **Keyword** - FTS5/BM25 over the chunk text, weighting `section_title` twice.
  Precise for exact terms, names, versions and numbers.
- **Semantic** - cosine similarity against `BAAI/bge-large-en-v1.5` embeddings,
  served through the Hugging Face Inference API. This is what answers a
  question whose wording never appears in the document.

Their scores are on different scales, so the two rankings are merged by
Reciprocal Rank Fusion, which uses only rank positions. A chunk found by one
channel alone still comes through - which is the point, because a question like
"what is this document about?" shares no keyword with the prose it asks about.

Questions about a document as a whole are handled separately: no single chunk
*is* the summary, so those also pull in a summary written at ingest plus the
document's opening chunks. That path is also the fallback whenever the two
channels find nothing, so an answer cites real passages rather than giving up.

Without `HF_TOKEN` the semantic channel is skipped and retrieval degrades to
keyword-only - it still works, but paraphrased questions will miss.

### Backfilling

Documents ingested before embeddings existed, or while the provider was
unreachable, have no vector and are invisible to semantic search. Repair them:

```bash
python -m scripts.backfill_embeddings            # fill in what is missing
python -m scripts.backfill_embeddings --summaries # summaries too
python -m scripts.backfill_embeddings --force     # after changing the model
```

To see why a question matched what it did:

```bash
python -m scripts.verify_retrieval "What is this document about?"
```

## Extraction notes

- **PDF** - PyMuPDF for text, fonts and reading order; pdfplumber for tables.
  Headings are inferred from font size and weight, running heads and page
  numbers are tagged as headers/footers, and paragraphs split across lines are
  rejoined. Text a table already captured is not stored twice.
- **DOCX** - text is read from the XML, so hyperlinks, text boxes and shapes are
  not missed. Headings come from styles or outline level, and tables, headers
  and footers are all captured.
- Scanned pages produce no text; their page numbers are listed in
  `ocr_required_pages`. Add OCR if you need those.
- `.doc` (legacy Word) is not supported - save as `.docx`.
