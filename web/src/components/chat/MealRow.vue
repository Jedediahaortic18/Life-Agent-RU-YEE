<template>
  <div class="flex items-start gap-2">
    <span class="text-sm mt-0.5 shrink-0">{{ icon }}</span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-1.5 mb-0.5">
        <span class="text-xs font-medium text-gray-600">{{ label }}</span>
        <span v-if="calories" class="text-xs text-orange-500">{{ calories }}kcal</span>
      </div>
      <div class="flex flex-wrap gap-1">
        <span
          v-for="item in normalizedItems"
          :key="item.name"
          class="text-xs px-1.5 py-0.5 bg-gray-50 rounded text-gray-700"
        >
          {{ item.name }}
          <span v-if="item.method" class="text-gray-400">· {{ item.method }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  icon: string
  label: string
  items: any[] | any
  calories?: number
}>()

const normalizedItems = computed(() => {
  if (!props.items) return []
  // 新格式：数组对象 [{name, cooking_method, ...}]
  if (Array.isArray(props.items)) {
    return props.items.map((item: any) => ({
      name: item.name ?? item.dish ?? String(item),
      method: item.cooking_method ?? '',
    }))
  }
  // 旧格式：{dish, calories, ingredients}
  if (props.items.dish) {
    return [{ name: props.items.dish, method: '' }]
  }
  return []
})
</script>
