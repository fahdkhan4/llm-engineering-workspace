import type { FileType, SourceRef } from '@/types/api'

/**
 * DOCX extraction has no page model: `helper/docx_extractor.py` writes
 * `page_number=1` for every block, so `page_start`/`page_end` on a DOCX chunk
 * are placeholders. Showing them would be a misleading citation, so page
 * information is only ever rendered for PDFs.
 */
export function hasReliablePages(fileType: FileType | null | undefined): boolean {
  return fileType === 'pdf'
}

export function pageLabel(source: SourceRef, fileType: FileType | null | undefined): string | null {
  if (!hasReliablePages(fileType)) return null
  if (!source.page_start) return null
  return source.page_start === source.page_end
    ? `Page ${source.page_start}`
    : `Pages ${source.page_start}–${source.page_end}`
}

/**
 * BM25 scores are unbounded, so absolute values mean little. Relevance is shown
 * relative to the best hit in the same answer.
 */
export function relativeRelevance(source: SourceRef, sources: SourceRef[]): number {
  const scores = sources.map((item) => item.score)
  const best = Math.max(...scores)
  const worst = Math.min(...scores)
  if (!Number.isFinite(best) || best <= 0) return 0
  if (best === worst) return 1
  return Math.max(0.08, (source.score - worst) / (best - worst))
}

export function relevanceLabel(ratio: number): string {
  if (ratio >= 0.75) return 'Top match'
  if (ratio >= 0.4) return 'Strong match'
  return 'Related'
}

/* -------------------------------------------------------------------------- *
 * Answer parsing
 *
 * The model cites passages by number ("...60 days of notice [3]."), and the
 * numbers match `SourceRef.index`. Parsing them out here lets the UI render
 * each marker as a link to the exact passage it came from, instead of leaving
 * a wall of bracketed file names in the prose.
 * -------------------------------------------------------------------------- */

export interface AnswerToken {
  kind: 'text' | 'citation'
  text: string
  /** Set on citation tokens only. */
  source?: SourceRef
}

export type AnswerBlock =
  | { kind: 'paragraph'; tokens: AnswerToken[] }
  | { kind: 'list'; items: AnswerToken[][] }
  /** The "what the documents do not cover" line, shown as a caveat. */
  | { kind: 'caveat'; tokens: AnswerToken[] }

/** `[3]`, `[2][5]`, `[1, 4]` — one or more source numbers. */
const MARKER_RE = /\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]/g
const BULLET_RE = /^[-*•]\s+/
const CAVEAT_RE = /^not (in|supported by) the documents\b/i

/**
 * The prompt asks for plain text, but models drift back into markdown. Strip
 * the emphasis markers so stray asterisks never reach the reader.
 */
function stripEmphasis(text: string): string {
  return text
    .replace(/\*\*([^*\n]+)\*\*/g, '$1')
    .replace(/__([^_\n]+)__/g, '$1')
    .replace(/\*([^*\n]+)\*/g, '$1')
}

export function tokenizeAnswer(line: string, sources: SourceRef[]): AnswerToken[] {
  // Threads stored before sources carried an index fall back to their position.
  const byIndex = new Map<number, SourceRef>(
    sources.map((source, position) => [source.index ?? position + 1, source] as [number, SourceRef]),
  )
  const tokens: AnswerToken[] = []
  let cursor = 0

  for (const match of line.matchAll(MARKER_RE)) {
    const at = match.index ?? 0
    const numbers = match[1].split(/[,;]/).map((part) => Number(part.trim()))
    const resolved = numbers.map((number) => byIndex.get(number))
    // A marker naming a source we do not have stays plain text: never render a
    // chip that leads nowhere.
    if (resolved.some((source) => !source)) continue

    const before = stripEmphasis(line.slice(cursor, at)).replace(/\s+$/, '')
    if (before) tokens.push({ kind: 'text', text: before })
    for (const source of resolved as SourceRef[]) {
      tokens.push({ kind: 'citation', text: String(source.index), source })
    }
    cursor = at + match[0].length
  }

  const tail = stripEmphasis(line.slice(cursor))
  if (tail) tokens.push({ kind: 'text', text: tail })
  return tokens
}

/** Split an answer into paragraphs, bullet lists and the trailing caveat. */
export function parseAnswer(content: string, sources: SourceRef[]): AnswerBlock[] {
  const blocks: AnswerBlock[] = []
  let paragraph: string[] = []
  let items: AnswerToken[][] = []

  const flushParagraph = () => {
    const text = paragraph.join(' ').trim()
    paragraph = []
    if (!text) return
    blocks.push({
      kind: CAVEAT_RE.test(text) ? 'caveat' : 'paragraph',
      tokens: tokenizeAnswer(text, sources),
    })
  }
  const flushList = () => {
    if (items.length) blocks.push({ kind: 'list', items })
    items = []
  }

  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line) {
      flushParagraph()
      flushList()
      continue
    }
    if (BULLET_RE.test(line)) {
      flushParagraph()
      items.push(tokenizeAnswer(line.replace(BULLET_RE, ''), sources))
      continue
    }
    flushList()
    paragraph.push(line)
  }
  flushParagraph()
  flushList()
  return blocks
}
