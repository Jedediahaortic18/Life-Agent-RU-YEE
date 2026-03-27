<template>
  <nav class="flex items-center justify-around border-t border-gray-200 bg-white py-2 shrink-0">
    <router-link
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="flex flex-col items-center gap-0.5 text-xs"
      :class="$route.path === tab.to ? 'text-blue-600' : 'text-gray-500'"
    >
      <span class="text-lg">{{ tab.icon }}</span>
      <span>{{ t(tab.labelKey) }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const tabs = [
  { to: '/', icon: '💬', labelKey: 'nav.chat' },
  // { to: '/devices', icon: '📱', labelKey: 'nav.devices' },
  { to: '/skillhub', icon: '🧩', labelKey: 'nav.skillhub' },
]
</script>
