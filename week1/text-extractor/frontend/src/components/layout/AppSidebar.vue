<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import AppIcon from '@/components/ui/AppIcon.vue'
import { useDocumentsStore } from '@/stores/documents'

export default defineComponent({
  name: 'AppSidebar',
  components: { AppIcon },
  emits: ['navigate'],
  data() {
    return {
      // Ordered as the workflow runs.
      links: [
        { to: '/overview', label: 'Overview', icon: 'layers' },
        { to: '/upload', label: 'Upload', icon: 'upload' },
        { to: '/library', label: 'Library', icon: 'library' },
        { to: '/chat', label: 'Ask', icon: 'chat' },
      ],
    }
  },
  computed: {
    ...mapState(useDocumentsStore, ['total']),
  },
})
</script>

<template>
  <aside class="sidebar">
    <RouterLink to="/overview" class="brand" @click="$emit('navigate')">
      <span class="brand-mark">
        <AppIcon name="layers" :size="17" :stroke-width="1.9" />
      </span>
      <span class="brand-name">Document Intelligence</span>
    </RouterLink>

    <nav class="nav" aria-label="Main">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="nav-link"
        @click="$emit('navigate')"
      >
        <span class="nav-indicator" aria-hidden="true" />
        <AppIcon :name="link.icon" :size="17" />
        <span class="nav-label">{{ link.label }}</span>
        <span v-if="link.to === '/library' && total > 0" class="nav-count">{{ total }}</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 226px;
  height: 100%;
  padding: 16px 12px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 22px;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--brand-gradient);
  color: #fff;
  box-shadow: var(--brand-glow);
}

.brand-name {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: -0.015em;
  line-height: 1.25;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  height: 36px;
  padding: 0 10px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  transition: background var(--transition), color var(--transition);
}

.nav-indicator {
  position: absolute;
  left: -12px;
  top: 50%;
  width: 3px;
  height: 0;
  border-radius: 0 3px 3px 0;
  background: var(--brand-gradient);
  transform: translateY(-50%);
  transition: height var(--transition-slow);
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-link.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
}

.nav-link.router-link-active .nav-indicator {
  height: 18px;
}

.nav-label {
  font-size: 13.5px;
  font-weight: 500;
}

.nav-link.router-link-active .nav-label {
  font-weight: 600;
}

.nav-count {
  margin-left: auto;
  padding: 0 7px;
  height: 19px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--bg-muted);
  color: var(--text-tertiary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.nav-link.router-link-active .nav-count {
  background: var(--bg-surface);
  color: var(--accent);
}
</style>
