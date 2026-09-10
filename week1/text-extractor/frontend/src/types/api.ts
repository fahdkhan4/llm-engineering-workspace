/**
 * Mirrors the FastAPI schemas in `schema/document_schema.py` and
 * `schema/chat_schema.py`. Keep these in sync with the backend.
 */

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type FileType = 'pdf' | 'docx'

/** `DocumentSummary` — what `GET /documents` returns per row. */
export interface DocumentSummary {
  id: number
  filename: string
  file_type: FileType
  file_size: number
  title: string | null
  author: string | null
  page_count: number
  word_count: number
  status: DocumentStatus
  created_at: string
}

/** `DocumentDetail` — `GET /documents/{id}`, and the `document` on an upload. */
export interface DocumentDetail extends DocumentSummary {
  subject: string | null
  keywords: string | null
  char_count: number
  extra_metadata: Record<string, unknown>
  /** Pages with no extractable text; scans that would need OCR to be searchable. */
  ocr_required_pages: number[]
  error_message: string | null
}

export interface ExtractionCounts {
  blocks: number
  tables: number
  chunks: number
}

/** `UploadResponse` — `POST /`. */
export interface UploadResponse {
  document: DocumentDetail
  counts: ExtractionCounts
  /** True when the same bytes were already uploaded, so nothing was re-parsed. */
  already_processed: boolean
}

/** `DocumentListResponse` — `GET /documents`. */
export interface DocumentListResponse {
  items: DocumentSummary[]
  total: number
  limit: number
  offset: number
}

/** `SourceRef` — one retrieved chunk backing an answer. */
export interface SourceRef {
  /** 1-based. The answer cites this passage as `[index]`. */
  index: number
  chunk_id: number
  document_id: number
  document_name: string
  section_title: string | null
  page_start: number
  page_end: number
  score: number
  excerpt: string
}

/** `AnswerResponse` — `GET /`. */
export interface AnswerResponse {
  question: string
  answer: string
  session_key: string
  sources: SourceRef[]
  model: string | null
  /** False while `llm/llm_client.py` is still the stub. */
  llm_configured: boolean
}

export interface HealthResponse {
  status: string
}

export interface AskParams {
  question: string
  document_id?: number | null
  session_key?: string | null
  top_k?: number | null
}
