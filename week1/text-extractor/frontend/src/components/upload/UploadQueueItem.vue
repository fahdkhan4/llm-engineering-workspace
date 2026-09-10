<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import SpinnerDot from '@/components/ui/SpinnerDot.vue'
import type { UploadItem } from '@/stores/uploads'
import { formatBytes, formatPageRanges } from '@/utils/format'

import ExtractionSummary from './ExtractionSummary.vue'

const STATE_LABELS: Record<string, string> = {
  queued: 'Waiting',
  uploading: 'Uploading',
  processing: 'Extracting',
  completed: 'Completed',
  duplicate: 'Already in your library',
  rejected: 'Not accepted',
  failed: 'Failed',
}

export default defineComponent({
  name: 'UploadQueueItem',
  components: { AlertPanel, AppIcon, ExtractionSummary, FileTypeBadge, SpinnerDot },
  props: {
    item: { type: Object as PropType<UploadItem>, required: true },
  },
  emits: ['remove', 'retry', 'open', 'ask'],
  computed: {
    label(): string {
      return STATE_LABELS[this.item.state] ?? this.item.state
    },

    isBusy(): boolean {
      return this.item.state === 'uploading' || this.item.state === 'processing'
    },

    isFinished(): boolean {
      return this.item.state === 'completed' || this.item.state === 'duplicate'
    },

    badgeClass(): string {
      switch (this.item.state) {
        case 'completed':
          return 'badge-success'
        case 'duplicate':
          return 'badge-info'
        case 'failed':
        case 'rejected':
          return 'badge-danger'
        case 'uploading':
        case 'processing':
          return 'badge-accent'
        default:
          return 'badge-neutral'
      }
    },

    ocrPages(): string {
      const pages = this.item.document?.ocr_required_pages ?? []
      return pages.length ? formatPageRanges(pages) : ''
    },
  },
  methods: {
    formatBytes,
  },
})
</script>

<template>
  <li class="queue-item" :class="item.state">
    <div class="head">
      <span class="glyph" :class="item.fileType">
        <SpinnerDot v-if="isBusy" :size="16" />
        <AppIcon v-else-if="item.state === 'completed'" name="check" :size="16" />
        <AppIcon v-else-if="item.state === 'duplicate'" name="layers" :size="16" />
        <AppIcon v-else-if="item.state === 'failed' || item.state === 'rejected'" name="alert" :size="16" />
        <AppIcon v-else name="file-text" :size="16" />
      </span>

      <div class="head-text">
        <p class="name" :title="item.name">{{ item.name }}</p>
        <p class="sub">
          <FileTypeBadge :file-type="item.fileType" />
          <span>{{ formatBytes(item.size) }}</span>
        </p>
      </div>

      <span class="badge" :class="badgeClass">{{ label }}</span>

      <button
        v-if="!isBusy"
        class="btn btn-ghost btn-icon"
        type="button"
        aria-label="Remove from list"
        @click="$emit('remove', item.id)"
      >
        <AppIcon name="close" :size="15" />
      </button>
    </div>

    <!-- The backend extracts synchronously, so there is no real progress to show. -->
    <div v-if="isBusy" class="progress" role="progressbar" aria-label="Extracting document">
      <span class="progress-bar" />
    </div>
    <p v-if="isBusy" class="busy-note">Large documents take a few seconds.</p>

    <AlertPanel
      v-if="item.state === 'rejected' || item.state === 'failed'"
      tone="danger"
      class="item-alert"
    >
      {{ item.error }}
      <template v-if="item.state === 'failed'" #actions>
        <button class="btn btn-sm btn-secondary" type="button" @click="$emit('retry', item.id)">
          Try again
        </button>
      </template>
    </AlertPanel>

    <div v-if="isFinished && item.document" class="result">
      <AlertPanel v-if="item.state === 'duplicate'" tone="info" class="item-alert">
        Already in your library — nothing was re-processed.
      </AlertPanel>

      <ExtractionSummary :document="item.document" :counts="item.counts" />

      <AlertPanel v-if="ocrPages" tone="warning" title="Some pages contain no extractable text">
        Page{{ item.document.ocr_required_pages.length > 1 ? 's' : '' }} {{ ocrPages }} appear
        to be scanned images and cannot be searched or cited.
      </AlertPanel>

      <div class="result-actions">
        <button class="btn btn-secondary btn-sm" type="button" @click="$emit('open', item)">
          <AppIcon name="file-text" :size="14" />
          Open document
        </button>
        <button class="btn btn-primary btn-sm" type="button" @click="$emit('ask', item)">
          <AppIcon name="chat" :size="14" />
          Ask about it
        </button>
      </div>
    </div>
  </li>
</template>

<style scoped>
.queue-item {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  transition: border-color var(--transition);
}

.queue-item.completed {
  border-color: var(--green-100);
}

.queue-item.failed,
.queue-item.rejected {
  border-color: var(--red-100);
}

.head {
  display: flex;
  align-items: center;
  gap: 11px;
}

.glyph {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}

.completed .glyph {
  background: var(--green-50);
  border-color: var(--green-100);
  color: var(--green-700);
}

.duplicate .glyph {
  background: var(--blue-50);
  border-color: var(--blue-100);
  color: var(--blue-700);
}

.failed .glyph,
.rejected .glyph {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.uploading .glyph,
.processing .glyph {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
  color: var(--accent);
}

.head-text {
  flex: 1;
  min-width: 0;
}

.name {
  font-size: 13.5px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sub {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.progress {
  height: 3px;
  margin-top: 13px;
  border-radius: 999px;
  background: var(--bg-muted);
  overflow: hidden;
}

.progress-bar {
  display: block;
  width: 34%;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
  animation: indeterminate 1.15s ease-in-out infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(320%); }
}

.busy-note {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.item-alert {
  margin-top: 13px;
}

.result {
  display: flex;
  flex-direction: column;
  gap: 13px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
