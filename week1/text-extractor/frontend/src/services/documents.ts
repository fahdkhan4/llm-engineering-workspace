import type {
  DocumentDetail,
  DocumentListResponse,
  UploadResponse,
} from '@/types/api'

import { request } from './http'

/** `POST /` — upload one PDF/.docx; the backend extracts it synchronously. */
export function uploadDocument(file: File, signal?: AbortSignal): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<UploadResponse>('/', { method: 'POST', body: form, signal })
}

/** `GET /documents` — newest first. */
export function listDocuments(
  limit = 25,
  offset = 0,
  signal?: AbortSignal,
): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/documents', { query: { limit, offset }, signal })
}

/** `GET /documents/{id}` — metadata only; see `getDocumentContent`. */
export function getDocument(id: number, signal?: AbortSignal): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/documents/${id}`, { signal })
}

/** `DELETE /documents/{id}` — permanent, cascades to blocks/tables/chunks. */
export function deleteDocument(id: number): Promise<void> {
  return request<void>(`/documents/${id}`, { method: 'DELETE' })
}
