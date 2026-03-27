<template>
  <div class="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2">
    <div v-html="rendered" />
    <span v-if="streaming" class="inline-block w-1.5 h-4 bg-gray-600 animate-pulse ml-0.5 align-text-bottom" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ content: string; streaming?: boolean }>()

const rendered = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content, { async: false }) as string
})
</script>
