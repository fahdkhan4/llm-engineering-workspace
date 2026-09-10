<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import { useDocumentsStore } from '@/stores/documents'
import type { FileType, SourceRef } from '@/types/api'
import { pageLabel } from '@/utils/citations'

const CARD_WIDTH = 340
const GAP = 10

/**
 * A `[3]` marker in an answer, rendered as the passage it stands for.
 *
 * Hovering shows the exact text the sentence was built from; clicking opens
 * that passage in the source list below the answer. The preview is teleported
 * and positioned with `fixed`, because the chat column scrolls and an absolute
 * popover would be clipped by it.
 */
export default defineComponent({
  name: 'CitationMark',
  components: { AppIcon, FileTypeBadge },
  props: {
    source: { type: Object as PropType<SourceRef>, required: true },
    /** True while this passage is the one highlighted in the source list. */
    active: { type: Boolean, default: false },
  },
  emits: ['select'],
  data() {
    return { open: false, top: 0, left: 0, above: false }
  },
  computed: {
    fileType(): FileType | null {
      return useDocumentsStore().fileTypeById(this.source.document_id)
    },

    /** Omitted for DOCX, where page numbers are placeholders. */
    pages(): string | null {
      return pageLabel(this.source, this.fileType)
    },

    label(): string {
      const where = [this.source.document_name, this.source.section_title, this.pages]
        .filter(Boolean)
        .join(', ')
      return `Source ${this.source.index}: ${where}`
    },
  },
  created() {
    // The preview needs the file type to decide whether pages can be shown.
    void useDocumentsStore().ensureFileType(this.source.document_id)
  },
  beforeUnmount() {
    this.detach()
  },
  methods: {
    show() {
      const chip = this.$refs.chip as HTMLElement | undefined
      if (!chip) return
      const rect = chip.getBoundingClientRect()

      this.above = rect.top > window.innerHeight / 2
      this.top = this.above ? rect.top - GAP : rect.bottom + GAP
      this.left = Math.min(
        Math.max(GAP, rect.left + rect.width / 2 - CARD_WIDTH / 2),
        Math.max(GAP, window.innerWidth - CARD_WIDTH - GAP),
      )
      this.open = true
      window.addEventListener('scroll', this.hide, true)
    },

    hide() {
      this.open = false
      this.detach()
    },

    detach() {
      window.removeEventListener('scroll', this.hide, true)
    },
  },
})
</script>

<template>
  <span class="cite-wrap">
    <button
      ref="chip"
      type="button"
      class="cite"
      :class="{ active }"
      :aria-label="label"
      @mouseenter="show"
      @mouseleave="hide"
      @focus="show"
      @blur="hide"
      @click="$emit('select', source)"
    >
      {{ source.index }}
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        class="cite-card"
        :class="{ above }"
        :style="{ top: `${top}px`, left: `${left}px` }"
        role="tooltip"
      >
        <div class="cite-head">
          <span class="cite-badge">{{ source.index }}</span>
          <span class="cite-doc">{{ source.document_name }}</span>
          <FileTypeBadge v-if="fileType" :file-type="fileType" />
        </div>

        <div v-if="source.section_title || pages" class="cite-meta">
          <span v-if="source.section_title" class="cite-where">
            <AppIcon name="book" :size="11" />
            {{ source.section_title }}
          </span>
          <span v-if="pages" class="cite-where">
            <AppIcon name="file-text" :size="11" />
            {{ pages }}
          </span>
        </div>

        <blockquote class="cite-excerpt">{{ source.excerpt }}</blockquote>

        <div class="cite-foot">
          <AppIcon name="target" :size="11" />
          Click to open this passage
        </div>
      </div>
    </Teleport>
  </span>
</template>

<style scoped>
.cite-wrap {
  position: relative;
  display: inline;
}

.cite {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  margin: 0 1px 0 2px;
  border: 1px solid var(--accent-soft-border);
  border-radius: 5px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 10.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  vertical-align: 1.5px;
  cursor: pointer;
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.cite:hover,
.cite:focus-visible,
.cite.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  transform: translateY(-1px);
}

.cite-card {
  position: fixed;
  z-index: 60;
  width: 340px; /* keep in sync with CARD_WIDTH */
  padding: 11px 12px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  box-shadow: var(--shadow-xl);
  pointer-events: none;
  animation: cite-in 120ms ease-out;
}

.cite-card.above {
  transform: translateY(-100%);
}

@keyframes cite-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.cite-head {
  display: flex;
  align-items: center;
  gap: 7px;
}

.cite-badge {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 5px;
  background: var(--accent);
  color: #fff;
  font-size: 10.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.cite-doc {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.cite-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 5px;
}

.cite-where {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--text-tertiary);
}

.cite-excerpt {
  max-height: 132px;
  margin-top: 9px;
  padding: 8px 10px;
  border-left: 2px solid var(--accent-soft-border);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--bg-subtle);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow: hidden;
  /* The excerpt is already truncated server-side; fade whatever still spills. */
  mask-image: linear-gradient(to bottom, #000 76%, transparent 100%);
}

.cite-foot {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--text-tertiary);
}

@media (max-width: 560px) {
  .cite-card {
    display: none;
  }
}
</style>
