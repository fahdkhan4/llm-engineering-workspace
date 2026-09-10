<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import { useDocumentsStore } from '@/stores/documents'
import type { FileType, SourceRef } from '@/types/api'
import { pageLabel, relativeRelevance, relevanceLabel } from '@/utils/citations'

export default defineComponent({
  name: 'SourceCard',
  components: { AppIcon, FileTypeBadge },
  props: {
    source: { type: Object as PropType<SourceRef>, required: true },
    /** All sources for the same answer — relevance is shown relative to them. */
    siblings: { type: Array as PropType<SourceRef[]>, required: true },
    index: { type: Number, required: true },
    /** Scroll target for the matching `[n]` marker in the answer. */
    anchorId: { type: String, default: '' },
    /** True while a marker for this passage was just clicked. */
    highlighted: { type: Boolean, default: false },
    /** False when retrieval returned this passage but the answer never used it. */
    quoted: { type: Boolean, default: true },
  },
  computed: {
    fileType(): FileType | null {
      return useDocumentsStore().fileTypeById(this.source.document_id)
    },

    /** Omitted entirely for DOCX, where page numbers are placeholders. */
    pages(): string | null {
      return pageLabel(this.source, this.fileType)
    },

    relevance(): number {
      return relativeRelevance(this.source, this.siblings)
    },

    relevanceText(): string {
      return relevanceLabel(this.relevance)
    },
  },
  created() {
    // The card needs the file type to decide whether pages can be cited.
    void useDocumentsStore().ensureFileType(this.source.document_id)
  },
})
</script>

<template>
  <article :id="anchorId || undefined" class="source-card" :class="{ highlighted, unquoted: !quoted }">
    <div class="card-head">
      <span class="index">{{ index }}</span>

      <div class="head-text">
        <RouterLink :to="`/documents/${source.document_id}`" class="doc-name">
          {{ source.document_name }}
        </RouterLink>
        <div class="locators">
          <FileTypeBadge v-if="fileType" :file-type="fileType" />
          <span v-if="source.section_title" class="section">
            <AppIcon name="book" :size="12" />
            {{ source.section_title }}
          </span>
          <span v-if="pages" class="pages">
            <AppIcon name="file-text" :size="12" />
            {{ pages }}
          </span>
          <span v-if="!quoted" class="unused">not used in the answer</span>
        </div>
      </div>

      <div class="relevance" :title="`Relevance score ${source.score}`">
        <span class="relevance-label">{{ relevanceText }}</span>
        <span class="relevance-bar">
          <span class="relevance-fill" :style="{ width: `${Math.round(relevance * 100)}%` }" />
        </span>
      </div>
    </div>

    <blockquote class="excerpt">{{ source.excerpt }}</blockquote>
  </article>
</template>

<style scoped>
.source-card {
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.source-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-xs);
}

/* Retrieved but never cited: present for transparency, visually secondary. */
.source-card.unquoted {
  opacity: 0.66;
}

.source-card.unquoted:hover {
  opacity: 1;
}

.source-card.highlighted {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  animation: source-flash 620ms ease-out;
}

@keyframes source-flash {
  0% {
    box-shadow: 0 0 0 0 var(--accent-soft-border);
  }
  40% {
    box-shadow: 0 0 0 7px var(--accent-soft);
  }
  100% {
    box-shadow: 0 0 0 3px var(--accent-soft);
  }
}

.unused {
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--bg-muted);
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.card-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.index {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: 5px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.head-text {
  flex: 1;
  min-width: 0;
}

.doc-name {
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
  transition: color var(--transition);
}

.doc-name:hover {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.locators {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.section,
.pages {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--text-tertiary);
  min-width: 0;
}

.section {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

.pages {
  font-variant-numeric: tabular-nums;
}

.relevance {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
  padding-top: 1px;
}

.relevance-label {
  font-size: 10.5px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.relevance-bar {
  display: block;
  width: 46px;
  height: 3px;
  border-radius: 999px;
  background: var(--bg-muted);
  overflow: hidden;
}

.relevance-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--brand-gradient);
  transition: width 380ms cubic-bezier(0.4, 0, 0.2, 1);
}

.excerpt {
  position: relative;
  margin-top: 11px;
  padding: 9px 12px 9px 13px;
  border-left: 2px solid var(--accent-soft-border);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--bg-subtle);
  font-size: 12.5px;
  line-height: 1.62;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

@media (max-width: 560px) {
  .relevance {
    display: none;
  }
}
</style>
