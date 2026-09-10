<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import { ACCEPT_ATTRIBUTE, MAX_UPLOAD_MB } from '@/utils/files'

export default defineComponent({
  name: 'UploadDropzone',
  components: { AppIcon },
  props: {
    disabled: { type: Boolean, default: false },
  },
  emits: ['files'],
  data() {
    return {
      dragging: false,
      // dragenter/dragleave fire for child elements too; count to avoid flicker.
      dragDepth: 0,
      accept: ACCEPT_ATTRIBUTE,
      maxMb: MAX_UPLOAD_MB,
    }
  },
  methods: {
    openPicker() {
      if (this.disabled) return
      ;(this.$refs.input as HTMLInputElement).click()
    },

    onSelect(event: Event) {
      const input = event.target as HTMLInputElement
      this.emitFiles(Array.from(input.files ?? []))
      input.value = ''
    },

    onDragEnter() {
      if (this.disabled) return
      this.dragDepth += 1
      this.dragging = true
    },

    onDragLeave() {
      this.dragDepth = Math.max(0, this.dragDepth - 1)
      if (this.dragDepth === 0) this.dragging = false
    },

    onDrop(event: DragEvent) {
      this.dragDepth = 0
      this.dragging = false
      if (this.disabled) return
      this.emitFiles(Array.from(event.dataTransfer?.files ?? []))
    },

    emitFiles(files: File[]) {
      if (files.length) this.$emit('files', files)
    },
  },
})
</script>

<template>
  <div
    class="dropzone"
    :class="{ dragging, disabled }"
    role="button"
    tabindex="0"
    :aria-disabled="disabled"
    aria-label="Upload PDF or Word documents"
    @click="openPicker"
    @keydown.enter.prevent="openPicker"
    @keydown.space.prevent="openPicker"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <input
      ref="input"
      class="sr-only"
      type="file"
      multiple
      :accept="accept"
      :disabled="disabled"
      @change="onSelect"
    />

    <div class="glyph">
      <AppIcon name="upload" :size="22" :stroke-width="1.6" />
    </div>

    <p class="headline">
      <span class="link">Choose files</span> or drag them here
    </p>
    <p class="hint">PDF and Word .docx · up to {{ maxMb }} MB each</p>

    <div class="formats">
      <span class="format pdf">PDF</span>
      <span class="format docx">DOCX</span>
    </div>
  </div>
</template>

<style scoped>
.dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 52px 24px;
  border: 1.5px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  cursor: pointer;
  text-align: center;
  overflow: hidden;
  transition: border-color var(--transition), background var(--transition),
    box-shadow var(--transition), transform var(--transition);
}

/* Brand wash that fades in on hover, behind the content. */
.dropzone::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--brand-wash);
  opacity: 0;
  transition: opacity var(--transition-slow);
  pointer-events: none;
}

.dropzone:hover:not(.disabled) {
  border-color: var(--accent);
  box-shadow: var(--shadow-card);
}

.dropzone:hover:not(.disabled)::before {
  opacity: 0.6;
}

.dropzone.dragging {
  border-color: var(--accent);
  border-style: solid;
  box-shadow: var(--brand-glow-strong);
  transform: scale(1.006);
}

.dropzone.dragging::before {
  opacity: 1;
}

.dropzone > * {
  position: relative;
}

.dropzone.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.glyph {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  margin-bottom: 16px;
  border-radius: 14px;
  background: var(--brand-gradient);
  border: 1px solid transparent;
  color: #fff;
  box-shadow: var(--brand-glow);
  transition: transform var(--transition-slow), box-shadow var(--transition);
}

.dropzone:hover:not(.disabled) .glyph {
  transform: translateY(-2px);
  box-shadow: var(--brand-glow-strong);
}

.dragging .glyph {
  transform: translateY(-4px) scale(1.04);
}

.headline {
  font-size: 15px;
  font-weight: 550;
}

.link {
  color: var(--accent);
  font-weight: 600;
}

.hint {
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.formats {
  display: flex;
  gap: 6px;
  margin-top: 16px;
}

.format {
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.04em;
}

.format.pdf {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.format.docx {
  background: var(--blue-50);
  border-color: var(--blue-100);
  color: var(--blue-700);
}
</style>
