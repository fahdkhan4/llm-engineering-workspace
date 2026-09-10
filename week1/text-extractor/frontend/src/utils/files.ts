import type { FileType } from '@/types/api'

/** Mirrors `settings.max_upload_mb`; the backend rejects anything larger. */
export const MAX_UPLOAD_MB = 25
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

export const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

export const ACCEPT_ATTRIBUTE = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export interface FileValidationResult {
  valid: boolean
  reason?: string
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.')
  return index === -1 ? '' : name.slice(index).toLowerCase()
}

/**
 * Client-side gate matching `helper/file_utils.detect_file_type`. The backend
 * still verifies the actual bytes; this only avoids a pointless round trip.
 */
export function validateFile(file: File): FileValidationResult {
  const extension = extensionOf(file.name)

  if (extension === '.doc') {
    return {
      valid: false,
      reason: 'Legacy .doc files are not supported. Save the file as .docx and try again.',
    }
  }

  const looksSupported =
    extension === '.pdf' || extension === '.docx' || ACCEPTED_MIME_TYPES.includes(file.type)

  if (!looksSupported) {
    return { valid: false, reason: 'Unsupported file type. Upload a PDF or a Word .docx file.' }
  }

  if (file.size === 0) {
    return { valid: false, reason: 'This file is empty.' }
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return { valid: false, reason: `This file is larger than the ${MAX_UPLOAD_MB} MB limit.` }
  }

  return { valid: true }
}

export function guessFileType(file: File): FileType {
  return extensionOf(file.name) === '.docx' || file.type.includes('wordprocessingml')
    ? 'docx'
    : 'pdf'
}
