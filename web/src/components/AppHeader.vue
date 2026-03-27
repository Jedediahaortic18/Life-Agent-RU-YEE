<template>
  <header class="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
    <h1 class="text-lg font-semibold text-gray-900">{{ title }}</h1>
    <span
      class="inline-flex items-center gap-1.5 text-xs"
      :class="online ? 'text-green-600' : 'text-gray-400'"
    >
      <span class="w-2 h-2 rounded-full" :class="online ? 'bg-green-500' : 'bg-gray-300'" />
      {{ online ? '在线' : '离线' }}
    </span>
  </header>
</template>

<script setup lang="ts">
defineProps<{ title: string; online: boolean }>()
</script>
