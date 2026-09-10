import type { DocumentContentResponse } from '@/types/content'

import { request } from './http'

/**
 * BACKEND GAP — the extracted body of a document is not exposed.
 *
 * `POST /` stores every block and table (`document_blocks`, `document_tables`),
 * but the only document endpoints are `GET /documents` and
 * `GET /documents/{id}`, and both return `DocumentSummary`/`DocumentDetail` —
 * metadata only. Nothing serves the content itself.
 *
 * This module is the seam for it, deliberately left unimplemented rather than
 * calling an endpoint that does not exist — the same way the backend ships
 * `llm/llm_client.py` as an explicit stub.
 *
 * To enable the reading view, add to the backend:
 *
 *     GET /documents/{id}/content -> {blocks: [...], tables: [...]}
 *
 * reading `document_blocks` ordered by `block_index` and `document_tables`
 * ordered by `table_index`. Then set `CONTENT_ENDPOINT_AVAILABLE` to true.
 * `DocumentContent.vue` already renders that response.
 */
export const CONTENT_ENDPOINT_AVAILABLE = false

export class ContentNotExposed extends Error {
  constructor() {
    super('The backend does not expose extracted document content yet.')
    this.name = 'ContentNotExposed'
  }
}

export function getDocumentContent(
  documentId: number,
  signal?: AbortSignal,
): Promise<DocumentContentResponse> {
  if (!CONTENT_ENDPOINT_AVAILABLE) return Promise.reject(new ContentNotExposed())
  return request<DocumentContentResponse>(`/documents/${documentId}/content`, { signal })
}
