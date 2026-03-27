<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4">
    <!-- 头部：名称 + 类型 + 状态 -->
    <div class="flex items-center gap-2 mb-1.5">
      <span class="font-medium text-sm text-gray-900 truncate">{{ name }}</span>
      <span class="text-xs px-2 py-0.5 rounded-full shrink-0" :class="typeColor">
        {{ type }}
      </span>
      <span
        v-if="verified"
        data-testid="verified-badge"
        class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 shrink-0"
      >
        已验证
      </span>
      <span
        v-if="status"
        class="text-xs px-2 py-0.5 rounded-full shrink-0"
        :class="status === 'loaded' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
      >
        {{ status }}
      </span>
      <span class="text-xs text-gray-400 ml-auto shrink-0">v{{ version }}</span>
    </div>

    <!-- 描述 -->
    <p v-if="description" class="text-xs text-gray-500 mb-2 line-clamp-2">{{ description }}</p>

    <!-- 作者 -->
    <p v-if="author" class="text-xs text-gray-400 mb-2">by {{ author }}</p>

    <!-- 标签 -->
    <div v-if="tags && tags.length" class="flex flex-wrap gap-1 mb-3">
      <span
        v-for="tag in tags"
        :key="tag"
        class="text-xs px-2 py-0.5 bg-gray-50 text-gray-600 rounded-full"
      >
        {{ tag }}
      </span>
    </div>

    <!-- 能力 (installed 模式) -->
    <div v-if="capabilities && capabilities.length" class="flex flex-wrap gap-1 mb-3">
      <span
        v-for="cap in capabilities"
        :key="cap"
        class="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full"
      >
        {{ cap }}
      </span>
    </div>

    <!-- 工具列表 -->
    <div v-if="tools && tools.length" class="flex flex-wrap gap-1 mb-3">
      <span
        v-for="tool in tools"
        :key="tool"
        class="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded"
      >
        {{ toolLabel(tool) }}
      </span>
    </div>

    <!-- 操作按钮 -->
    <div class="flex items-center gap-2">
      <!-- 市场模式 -->
      <template v-if="mode === 'market'">
        <span
          v-if="isInstalled"
          data-testid="installed-mark"
          class="text-xs text-green-600 font-medium"
        >
          已安装
        </span>
        <button
          v-else
          data-testid="install-btn"
          class="text-xs px-3 py-1 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors"
          :disabled="installing"
          @click="$emit('install', name)"
        >
          {{ installing ? '安装中...' : '安装' }}
        </button>
        <a
          v-if="repositoryUrl"
          data-testid="detail-link"
          :href="repositoryUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-xs text-blue-500 hover:underline ml-auto"
        >
          查看详情
        </a>
      </template>

      <!-- 已安装模式 -->
      <template v-if="mode === 'installed' && source === 'contrib'">
        <button
          data-testid="reload-btn"
          class="text-xs px-3 py-1 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          @click="$emit('reload', name)"
        >
          重载
        </button>
        <button
          data-testid="uninstall-btn"
          class="text-xs px-3 py-1 rounded-full border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
          @click="$emit('uninstall', name)"
        >
          卸载
        </button>
      </template>

      <!-- 来源标记 -->
      <span v-if="mode === 'installed'" class="text-xs text-gray-400 ml-auto">
        {{ source === 'builtin' ? '内置' : '社区' }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  name: string
  version: string
  type: string
  description?: string
  author?: string
  tags?: string[]
  capabilities?: string[]
  tools?: string[]
  status?: string
  verified?: boolean
  source?: 'builtin' | 'contrib'
  mode?: 'market' | 'installed'
  isInstalled?: boolean
  installing?: boolean
  repositoryUrl?: string
}>(), {
  description: '',
  author: '',
  tags: () => [],
  capabilities: () => [],
  tools: () => [],
  status: '',
  verified: false,
  source: 'builtin',
  mode: 'installed',
  isInstalled: false,
  installing: false,
  repositoryUrl: '',
})

defineEmits<{
  install: [name: string]
  uninstall: [name: string]
  reload: [name: string]
}>()

const typeColorMap: Record<string, string> = {
  agent: 'bg-blue-100 text-blue-700',
  memory: 'bg-purple-100 text-purple-700',
  search: 'bg-orange-100 text-orange-700',
  extension: 'bg-teal-100 text-teal-700',
}

const typeColor = computed(() => typeColorMap[props.type] ?? 'bg-gray-100 text-gray-600')

const TOOL_LABELS: Record<string, string> = {
  profile_get: '获取画像',
  profile_save: '保存画像',
  dish_query: '菜品查询',
  meal_recommend: '餐食规划',
  shopping_list: '购物清单',
  address_get: '查询地址',
  address_save: '保存地址',
  agent_call: 'Agent调用',
  agent_list: 'Agent列表',
  hema_set_location: '设置定位',
  hema_add_address: '新增地址',
  hema_search: '搜索商品',
  hema_add_cart: '加购物车',
  hema_cart_status: '购物车状态',
}

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
}
</script>
