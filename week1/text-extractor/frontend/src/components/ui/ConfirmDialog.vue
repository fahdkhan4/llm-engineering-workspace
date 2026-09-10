<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from './AppIcon.vue'
import SpinnerDot from './SpinnerDot.vue'

export default defineComponent({
  name: 'ConfirmDialog',
  components: { AppIcon, SpinnerDot },
  props: {
    open: { type: Boolean, default: false },
    title: { type: String, required: true },
    confirmLabel: { type: String, default: 'Confirm' },
    cancelLabel: { type: String, default: 'Cancel' },
    tone: { type: String, default: 'danger' },
    busy: { type: Boolean, default: false },
  },
  emits: ['confirm', 'cancel'],
  watch: {
    open(isOpen: boolean) {
      if (isOpen) {
        document.addEventListener('keydown', this.onKeydown)
        this.$nextTick(() => (this.$refs.confirmButton as HTMLButtonElement | undefined)?.focus())
      } else {
        document.removeEventListener('keydown', this.onKeydown)
      }
    },
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.onKeydown)
  },
  methods: {
    onKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !this.busy) this.$emit('cancel')
    },
  },
})
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div v-if="open" class="overlay" @click.self="!busy && $emit('cancel')">
        <div
          class="dialog"
          role="alertdialog"
          aria-modal="true"
          :aria-label="title"
        >
          <div class="glyph" :class="`tone-${tone}`">
            <AppIcon :name="tone === 'danger' ? 'alert' : 'info'" :size="19" />
          </div>
          <h2 class="title">{{ title }}</h2>
          <div class="body"><slot /></div>
          <div class="actions">
            <button class="btn btn-secondary" type="button" :disabled="busy" @click="$emit('cancel')">
              {{ cancelLabel }}
            </button>
            <button
              ref="confirmButton"
              class="btn"
              :class="tone === 'danger' ? 'btn-danger' : 'btn-primary'"
              type="button"
              :disabled="busy"
              @click="$emit('confirm')"
            >
              <SpinnerDot v-if="busy" :size="14" />
              {{ confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(12, 17, 27, 0.45);
  backdrop-filter: blur(2px);
}

.dialog {
  width: min(420px, 100%);
  padding: 24px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
}

.glyph {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin-bottom: 15px;
  border-radius: 10px;
  border: 1px solid;
}

.tone-danger {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.tone-info {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
  color: var(--accent);
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.body {
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: 13.5px;
  line-height: 1.6;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  margin-top: 22px;
}

.dialog-enter-active,
.dialog-leave-active {
  transition: opacity 160ms ease;
}

.dialog-enter-active .dialog,
.dialog-leave-active .dialog {
  transition: transform 180ms cubic-bezier(0.4, 0, 0.2, 1);
}

.dialog-enter-from,
.dialog-leave-to {
  opacity: 0;
}

.dialog-enter-from .dialog,
.dialog-leave-to .dialog {
  transform: scale(0.96) translateY(6px);
}
</style>
