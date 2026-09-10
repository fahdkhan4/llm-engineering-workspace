import type { AnswerResponse, AskParams } from '@/types/api'

import { request } from './http'

/**
 * `GET /` — answer a question from the extracted documents.
 *
 * `session_key` comes back on every answer and must be sent with the next
 * question to keep the thread going.
 */
export function askQuestion(params: AskParams, signal?: AbortSignal): Promise<AnswerResponse> {
  return request<AnswerResponse>('/', {
    query: {
      question: params.question,
      document_id: params.document_id ?? undefined,
      session_key: params.session_key ?? undefined,
      top_k: params.top_k ?? undefined,
    },
    signal,
  })
}
