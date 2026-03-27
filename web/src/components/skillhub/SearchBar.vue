<template>
  <div class="space-y-2">
    <!-- 搜索框 -->
    <div class="relative">
      <input
        v-model="query"
        type="text"
        placeholder="搜索插件..."
        class="w-full border border-gray-300 rounded-lg px-3 py-2 pl-9 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        @input="onInput"
      />
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
    </div>

    <!-- 类型筛选 -->
    <div class="flex gap-1.5 flex-wrap">
      <button
        v-for="t in typeOptions"
        :key="t.value"
        data-testid="type-filter"
        class="text-xs px-2.5 py-1 rounded-full border transition-colors"
        :class="selectedType === t.value
          ? 'bg-blue-600 text-white border-blue-600'
          : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'"
        @click="selectType(t.value)"
      >
        {{ t.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  search: [params: { q: string; tags: string; type: string }]
}>()

const query = ref('')
const selectedType = ref('')

const typeOptions = [
  { value: '', label: '全部' },
  { value: 'agent', label: 'Agent' },
  { value: 'memory', label: 'Memory' },
  { value: 'extension', label: 'Extension' },
]

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function emitSearch() {
  emit('search', {
    q: query.value.trim(),
    tags: '',
    type: selectedType.value,
  })
}

function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(emitSearch, 300)
}

function selectType(type: string) {
  selectedType.value = type
  emitSearch()
}
</script>
