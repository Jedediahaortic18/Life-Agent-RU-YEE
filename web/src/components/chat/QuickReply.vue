<template>
  <div class="flex flex-wrap gap-1.5 mt-2">
    <button
      v-for="option in options"
      :key="option"
      class="px-3 py-1.5 text-xs rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors cursor-pointer active:scale-95"
      :disabled="disabled"
      @click="$emit('select', option)"
    >
      {{ option }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ options: string[]; disabled?: boolean }>()
defineEmits<{ select: [value: string] }>()
</script>
