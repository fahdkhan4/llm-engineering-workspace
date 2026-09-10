/**
 * Shapes for the extracted body of a document.
 *
 * These mirror the `document_blocks` and `document_tables` tables in
 * `database/models.py`. The data is stored on upload but no endpoint returns
 * it yet — see `services/documentContent.ts`.
 */

export type BlockType =
  | 'heading'
  | 'paragraph'
  | 'list_item'
  | 'table'
  | 'header'
  | 'footer'
  | 'caption'

export interface DocumentBlock {
  id: number
  page_number: number
  block_index: number
  block_type: BlockType
  heading_level: number | null
  content: string
  meta: Record<string, unknown> & { table_index?: number }
}

export interface DocumentTable {
  id: number
  page_number: number
  table_index: number
  n_rows: number
  n_cols: number
  content_markdown: string
  content_json: string[][]
}

export interface DocumentContentResponse {
  blocks: DocumentBlock[]
  tables: DocumentTable[]
}

/** An entry in the heading-based table of contents. */
export interface OutlineEntry {
  id: number
  level: number
  title: string
  page: number
}
