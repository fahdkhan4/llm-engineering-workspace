<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import type { FileType } from '@/types/api'
import type { DocumentBlock, DocumentTable, OutlineEntry } from '@/types/content'

/**
 * Reading view for the extracted body of a document. Consecutive list items are
 * grouped, tables are rendered from `content_json`, and running headers/footers
 * are kept out of the flow so the text reads like the original.
 *
 * Rendered from the response documented in `services/documentContent.ts`.
 */

type Node =
  | { kind: 'heading'; key: string; block: DocumentBlock; level: number }
  | { kind: 'paragraph'; key: string; block: DocumentBlock }
  | { kind: 'caption'; key: string; block: DocumentBlock }
  | { kind: 'list'; key: string; items: DocumentBlock[] }
  | { kind: 'table'; key: string; page: number; table: DocumentTable | null }

export default defineComponent({
  name: 'DocumentContent',
  components: { AppIcon },
  props: {
    blocks: { type: Array as PropType<DocumentBlock[]>, required: true },
    tables: { type: Array as PropType<DocumentTable[]>, default: () => [] },
    fileType: { type: String as PropType<FileType>, required: true },
  },
  data() {
    return {
      activeHeadingId: null as number | null,
    }
  },
  computed: {
    /** PDF blocks carry real page numbers; DOCX blocks are all page 1. */
    showsPages(): boolean {
      return this.fileType === 'pdf'
    },

    ordered(): DocumentBlock[] {
      return [...this.blocks].sort((a, b) => a.block_index - b.block_index)
    },

    tableByIndex(): Record<number, DocumentTable> {
      return Object.fromEntries(this.tables.map((table) => [table.table_index, table]))
    },

    nodes(): Node[] {
      const result: Node[] = []
      let listBuffer: DocumentBlock[] = []

      const flushList = () => {
        if (!listBuffer.length) return
        result.push({ kind: 'list', key: `list-${listBuffer[0].id}`, items: listBuffer })
        listBuffer = []
      }

      for (const block of this.ordered) {
        // Running heads and page numbers are noise in a reading view.
        if (block.block_type === 'header' || block.block_type === 'footer') continue

        if (block.block_type === 'list_item') {
          listBuffer.push(block)
          continue
        }
        flushList()

        if (block.block_type === 'heading') {
          result.push({
            kind: 'heading',
            key: `h-${block.id}`,
            block,
            level: Math.min(Math.max(block.heading_level ?? 1, 1), 6),
          })
        } else if (block.block_type === 'table') {
          const index = block.meta?.table_index
          result.push({
            kind: 'table',
            key: `t-${block.id}`,
            page: block.page_number,
            table: typeof index === 'number' ? this.tableByIndex[index] ?? null : null,
          })
        } else if (block.block_type === 'caption') {
          result.push({ kind: 'caption', key: `c-${block.id}`, block })
        } else {
          result.push({ kind: 'paragraph', key: `p-${block.id}`, block })
        }
      }

      flushList()
      return result
    },

    outline(): OutlineEntry[] {
      return this.ordered
        .filter((block) => block.block_type === 'heading' && block.content.trim())
        .map((block) => ({
          id: block.id,
          level: Math.min(Math.max(block.heading_level ?? 1, 1), 4),
          title: block.content.trim(),
          page: block.page_number,
        }))
    },
  },
  methods: {
    headingTag(level: number): string {
      return `h${Math.min(level + 1, 6)}`
    },

    scrollToHeading(id: number) {
      const target = this.$refs[`heading-${id}`] as HTMLElement[] | HTMLElement | undefined
      const element = Array.isArray(target) ? target[0] : target
      if (!element) return
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      this.activeHeadingId = id
    },
  },
})
</script>

<template>
  <div class="content-layout" :class="{ 'has-outline': outline.length > 0 }">
    <nav v-if="outline.length" class="outline" aria-label="Table of contents">
      <p class="section-label outline-title">Contents</p>
      <ul class="outline-list">
        <li v-for="entry in outline" :key="entry.id" :class="`level-${entry.level}`">
          <button
            type="button"
            class="outline-link"
            :class="{ active: activeHeadingId === entry.id }"
            @click="scrollToHeading(entry.id)"
          >
            <span class="outline-text">{{ entry.title }}</span>
            <span v-if="showsPages" class="outline-page">{{ entry.page }}</span>
          </button>
        </li>
      </ul>
    </nav>

    <article class="reader">
      <template v-for="node in nodes" :key="node.key">
        <component
          :is="headingTag(node.level)"
          v-if="node.kind === 'heading'"
          :ref="`heading-${node.block.id}`"
          class="doc-heading"
          :class="`h-level-${node.level}`"
        >
          {{ node.block.content }}
        </component>

        <p v-else-if="node.kind === 'paragraph'" class="doc-paragraph">
          {{ node.block.content }}
        </p>

        <p v-else-if="node.kind === 'caption'" class="doc-caption">
          {{ node.block.content }}
        </p>

        <ul v-else-if="node.kind === 'list'" class="doc-list">
          <li v-for="item in node.items" :key="item.id">{{ item.content }}</li>
        </ul>

        <figure v-else-if="node.kind === 'table'" class="doc-table-wrap">
          <div v-if="node.table && node.table.content_json.length" class="doc-table-scroll">
            <table class="doc-table">
              <thead>
                <tr>
                  <th v-for="(cell, index) in node.table.content_json[0]" :key="index">
                    {{ cell }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in node.table.content_json.slice(1)" :key="rowIndex">
                  <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="doc-table-missing">
            <AppIcon name="table" :size="14" />
            A table was detected here but its cells were not captured.
          </p>
          <figcaption v-if="node.table" class="doc-table-caption">
            <AppIcon name="table" :size="12" />
            {{ node.table.n_rows }} × {{ node.table.n_cols }} table<span v-if="showsPages">
              · page {{ node.page }}</span
            >
          </figcaption>
        </figure>
      </template>
    </article>
  </div>
</template>

<style scoped>
.content-layout {
  display: grid;
  gap: 28px;
}

.content-layout.has-outline {
  grid-template-columns: 208px minmax(0, 1fr);
}

.outline {
  position: sticky;
  top: 16px;
  align-self: start;
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}

.outline-title {
  margin-bottom: 9px;
}

.outline-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-left: 1px solid var(--border);
}

.outline-link {
  display: flex;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  padding: 4px 8px;
  text-align: left;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--text-secondary);
  border-left: 2px solid transparent;
  margin-left: -1px;
  transition: color var(--transition), border-color var(--transition);
}

.outline-link:hover {
  color: var(--text-primary);
}

.outline-link.active {
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 500;
}

.outline-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.outline-page {
  font-size: 11px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.level-2 .outline-link { padding-left: 18px; }
.level-3 .outline-link { padding-left: 28px; font-size: 12px; }
.level-4 .outline-link { padding-left: 38px; font-size: 12px; }

.reader {
  max-width: 72ch;
  font-size: 14.5px;
  line-height: 1.72;
  color: var(--text-primary);
}

.doc-heading {
  scroll-margin-top: 20px;
  font-weight: 600;
  letter-spacing: -0.014em;
}

.h-level-1 {
  font-size: 21px;
  margin: 34px 0 12px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--border);
}

.h-level-2 { font-size: 17.5px; margin: 28px 0 10px; }
.h-level-3 { font-size: 15.5px; margin: 24px 0 8px; }
.h-level-4,
.h-level-5,
.h-level-6 {
  font-size: 14px;
  margin: 20px 0 6px;
  color: var(--text-secondary);
}

.reader > *:first-child {
  margin-top: 0;
}

.doc-paragraph {
  margin: 0 0 15px;
  overflow-wrap: break-word;
}

.doc-caption {
  margin: -6px 0 18px;
  font-size: 12.5px;
  color: var(--text-tertiary);
  font-style: italic;
}

.doc-list {
  margin: 0 0 16px;
  padding-left: 4px;
  list-style: none;
}

.doc-list li {
  position: relative;
  padding-left: 18px;
  margin-bottom: 5px;
}

.doc-list li::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 10px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.doc-table-wrap {
  margin: 0 0 22px;
}

.doc-table-scroll {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.doc-table th,
.doc-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  vertical-align: top;
}

.doc-table th:last-child,
.doc-table td:last-child {
  border-right: none;
}

.doc-table tbody tr:last-child td {
  border-bottom: none;
}

.doc-table th {
  background: var(--bg-subtle);
  font-weight: 600;
  font-size: 12.5px;
  white-space: nowrap;
}

.doc-table tbody tr:nth-child(even) {
  background: var(--bg-subtle);
}

.doc-table-missing {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 12px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.doc-table-caption {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--text-tertiary);
}

@media (max-width: 900px) {
  .content-layout.has-outline {
    grid-template-columns: minmax(0, 1fr);
  }

  .outline {
    position: static;
    max-height: none;
  }
}
</style>
