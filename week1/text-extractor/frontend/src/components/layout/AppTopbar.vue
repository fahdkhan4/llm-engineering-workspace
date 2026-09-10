<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import AppIcon from '@/components/ui/AppIcon.vue'
import { useHealthStore } from '@/stores/health'

export default defineComponent({
  name: 'AppTopbar',
  components: { AppIcon },
  emits: ['toggle-sidebar'],
  data() {
    return {
      theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light',
    }
  },
  computed: {
    ...mapState(useHealthStore, ['status', 'label', 'checking']),
    pageTitle(): string {
      return (this.$route.meta.title as string | undefined) ?? 'Workspace'
    },
  },
  methods: {
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      document.documentElement.setAttribute('data-theme', this.theme)
      localStorage.setItem('diw.theme', this.theme)
    },
    recheck() {
      void useHealthStore().refresh()
    },
  },
})
</script>

<template>
  <header class="topbar">
    <button
      class="btn btn-ghost btn-icon menu-button"
      type="button"
      aria-label="Toggle navigation"
      @click="$emit('toggle-sidebar')"
    >
      <AppIcon name="menu" :size="18" />
    </button>

    <h1 class="title">{{ pageTitle }}</h1>

    <div class="spacer" />

    <button
      class="health"
      :class="status"
      type="button"
      :title="`${label} — click to re-check`"
      @click="recheck"
    >
      <span class="health-dot" :class="{ checking }" />
      <span class="health-label">{{ label }}</span>
    </button>

    <button
      class="btn btn-ghost btn-icon"
      type="button"
      :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
      @click="toggleTheme"
    >
      <AppIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="17" />
    </button>

    <RouterLink class="btn btn-primary btn-sm upload-shortcut" to="/upload">
      <AppIcon name="upload" :size="15" />
      <span>Upload</span>
    </RouterLink>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 20px;
  background: color-mix(in srgb, var(--bg-surface) 82%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 20;
}

.title {
  font-size: 14.5px;
  font-weight: 650;
  letter-spacing: -0.015em;
  white-space: nowrap;
}

.menu-button {
  display: none;
}

.health {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-secondary);
  transition: border-color var(--transition), background var(--transition);
}

.health:hover {
  border-color: var(--border-strong);
}

.health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gray-400);
}

.health.online .health-dot {
  background: var(--green-500);
  box-shadow: 0 0 0 3px rgba(18, 183, 106, 0.16);
}

.health.offline {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.health.offline .health-dot {
  background: var(--red-500);
  box-shadow: 0 0 0 3px rgba(240, 68, 56, 0.16);
}

.health-dot.checking {
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@media (max-width: 900px) {
  .menu-button {
    display: inline-flex;
  }

  .health-label {
    display: none;
  }

  .health {
    padding: 0 9px;
  }
}

@media (max-width: 560px) {
  .upload-shortcut span {
    display: none;
  }
}
</style>
