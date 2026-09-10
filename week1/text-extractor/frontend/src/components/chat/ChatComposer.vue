<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import SpinnerDot from '@/components/ui/SpinnerDot.vue'
import type { DocumentSummary } from '@/types/api'

export default defineComponent({
  name: 'ChatComposer',
  components: { AppIcon, SpinnerDot },
  props: {
    documents: { type: Array as PropType<DocumentSummary[]>, required: true },
    documentId: { type: Number as PropType<number | null>, default: null },
    topK: { type: Number, required: true },
    sending: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    scopeLocked: { type: Boolean, default: false },
  },
  emits: ['send', 'update:documentId', 'update:topK'],
  data() {
    return {
      draft: '',
    }
  },
  computed: {
    canSend(): boolean {
      return this.draft.trim().length > 0 && !this.sending && !this.disabled
    },

    scopeValue: {
      get(): string {
        return this.documentId === null ? 'all' : String(this.documentId)
      },
      set(value: string) {
        this.$emit('update:documentId', value === 'all' ? null : Number(value))
      },
    },

    topKValue: {
      get(): number {
        return this.topK
      },
      set(value: number) {
        this.$emit('update:topK', Number(value))
      },
    },
  },
  methods: {
    submit() {
      if (!this.canSend) return
      this.$emit('send', this.draft.trim())
      this.draft = ''
      this.$nextTick(this.resize)
    },

    /** Grow with the question, up to a cap, then scroll. */
    resize() {
      const element = this.$refs.textarea as HTMLTextAreaElement | undefined
      if (!element) return
      element.style.height = 'auto'
      element.style.height = `${Math.min(element.scrollHeight, 180)}px`
    },

    focus() {
      ;(this.$refs.textarea as HTMLTextAreaElement | undefined)?.focus()
    },
  },
})
</script>

<template>
  <div class="composer" :class="{ disabled }">
    <div class="controls">
      <label class="control">
        <AppIcon name="target" :size="13" />
        <span class="control-label">Scope</span>
        <select
          v-model="scopeValue"
          class="control-select"
          :disabled="disabled"
          aria-label="Question scope"
        >
          <option value="all">Entire library</option>
          <option v-for="doc in documents" :key="doc.id" :value="String(doc.id)">
            {{ doc.filename }}
          </option>
        </select>
      </label>

      <span v-if="scopeLocked" class="scope-note">
        <AppIcon name="info" :size="12" />
        Changing scope starts a new conversation
      </span>

      <div class="spacer" />

      <label class="control">
        <span class="control-label">Passages</span>
        <select
          v-model.number="topKValue"
          class="control-select narrow"
          :disabled="disabled"
          aria-label="How many passages to retrieve"
        >
          <option v-for="value in [3, 4, 6, 8, 10, 15, 20]" :key="value" :value="value">
            {{ value }}
          </option>
        </select>
      </label>
    </div>

    <div class="input-row">
      <textarea
        ref="textarea"
        v-model="draft"
        class="textarea question"
        rows="1"
        :disabled="disabled"
        placeholder="Ask a question about your documents…"
        aria-label="Your question"
        @input="resize"
        @keydown.enter.exact.prevent="submit"
      />
      <button
        class="btn btn-primary send"
        type="button"
        :disabled="!canSend"
        aria-label="Send question"
        @click="submit"
      >
        <SpinnerDot v-if="sending" :size="15" />
        <AppIcon v-else name="arrow-up" :size="16" />
      </button>
    </div>

    <p class="hint">
      <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
    </p>
  </div>
</template>

<style scoped>
.composer {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.composer:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.composer.disabled {
  opacity: 0.65;
}

.controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 9px;
  flex-wrap: wrap;
}

.control {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-tertiary);
  min-width: 0;
}

.control-label {
  font-size: 11.5px;
  font-weight: 500;
}

.control-select {
  max-width: 220px;
  height: 24px;
  padding: 0 4px;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--transition);
}

.control-select:hover:not(:disabled) {
  background: var(--bg-muted);
}

.control-select:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.control-select.narrow {
  max-width: 62px;
}

.scope-note {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: 9px;
}

.question {
  flex: 1;
  border: none;
  background: transparent;
  padding: 4px 2px;
  font-size: 14px;
  max-height: 180px;
  overflow-y: auto;
}

.question:focus {
  outline: none;
  box-shadow: none;
}

.send {
  width: 34px;
  height: 34px;
  padding: 0;
  flex-shrink: 0;
  border-radius: var(--radius);
}

.hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-tertiary);
}

kbd {
  display: inline-block;
  padding: 0 4px;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 4px;
  background: var(--bg-subtle);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 15px;
}
</style>
