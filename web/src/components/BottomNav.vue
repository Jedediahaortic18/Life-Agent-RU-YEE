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
      <span>{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
const tabs = [
  { to: '/', icon: '💬', label: '对话' },
  // { to: '/devices', icon: '📱', label: '设备' },  // 暂时隐藏
  { to: '/skillhub', icon: '🧩', label: '扩展' },
]
</script>
