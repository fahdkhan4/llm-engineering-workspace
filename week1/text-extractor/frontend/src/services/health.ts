import type { HealthResponse } from '@/types/api'

import { request } from './http'

/** `GET /health` — backs the connection indicator in the top bar. */
export function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}
