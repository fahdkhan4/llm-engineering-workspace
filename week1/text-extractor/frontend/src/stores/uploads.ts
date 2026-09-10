import { defineStore } from 'pinia'

import { uploadDocument } from '@/services/documents'
import { ApiError } from '@/services/http'
import type { DocumentDetail, ExtractionCounts, FileType } from '@/types/api'
import { guessFileType, validateFile } from '@/utils/files'

/**
 * `POST /` extracts synchronously: the response only arrives once the document
 * is parsed and stored. There is no job id to poll, so "processing" is simply
 * the request being in flight — no progress is invented for it.
 */
export type UploadState =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'duplicate'
  | 'rejected'
  | 'failed'

export interface UploadItem {
  id: string
  file: File
  name: string
  size: number
  fileType: FileType
  state: UploadState
  error: string | null
  document: DocumentDetail | null
  counts: ExtractionCounts | null
}

let nextId = 1

function createItem(file: File): UploadItem {
  return {
    id: `upload-${nextId++}`,
    file,
    name: file.name,
    size: file.size,
    fileType: guessFileType(file),
    state: 'queued',
    error: null,
    document: null,
    counts: null,
  }
}

export const useUploadStore = defineStore('uploads', {
  state: () => ({
    items: [] as UploadItem[],
    running: false,
  }),

  getters: {
    hasItems: (state) => state.items.length > 0,
    pendingCount: (state) =>
      state.items.filter((item) => item.state === 'queued' || item.state === 'uploading' || item.state === 'processing')
        .length,
    completedItems: (state) => state.items.filter((item) => item.state === 'completed'),
    /** Files rejected before upload, so the reason is purely client-side. */
    rejectedItems: (state) => state.items.filter((item) => item.state === 'rejected'),
  },

  actions: {
    /** Validates locally first; invalid files are listed with their reason. */
    enqueue(files: File[]): UploadItem[] {
      const added = files.map((file) => {
        const item = createItem(file)
        const validation = validateFile(file)
        if (!validation.valid) {
          item.state = 'rejected'
          item.error = validation.reason ?? 'This file cannot be uploaded.'
        }
        this.items.push(item)
        return item
      })
      return added
    },

    remove(id: string) {
      this.items = this.items.filter((item) => item.id !== id)
    },

    clearFinished() {
      this.items = this.items.filter(
        (item) => item.state === 'queued' || item.state === 'uploading' || item.state === 'processing',
      )
    },

    reset() {
      this.items = []
    },

    /**
     * Uploads queued files one at a time: extraction is CPU-bound on the
     * backend, and serial uploads keep the per-file state honest.
     */
    async processQueue(onDocument?: (document: DocumentDetail) => void) {
      if (this.running) return
      this.running = true

      try {
        for (const item of this.items) {
          if (item.state !== 'queued') continue
          await this.uploadOne(item, onDocument)
        }
      } finally {
        this.running = false
      }
    },

    async uploadOne(item: UploadItem, onDocument?: (document: DocumentDetail) => void) {
      item.state = 'uploading'
      item.error = null

      try {
        // The request is one round trip; the server parses before responding.
        item.state = 'processing'
        const response = await uploadDocument(item.file)

        item.document = response.document
        item.counts = response.counts
        item.fileType = response.document.file_type
        item.state = response.already_processed ? 'duplicate' : 'completed'
        onDocument?.(response.document)
      } catch (error) {
        const apiError = error as ApiError
        item.state = 'failed'
        item.error = apiError.detail || 'The document could not be processed.'
      }
    },

    retry(id: string, onDocument?: (document: DocumentDetail) => void) {
      const item = this.items.find((entry) => entry.id === id)
      if (!item || item.state === 'uploading' || item.state === 'processing') return
      item.state = 'queued'
      item.error = null
      void this.processQueue(onDocument)
    },
  },
})
