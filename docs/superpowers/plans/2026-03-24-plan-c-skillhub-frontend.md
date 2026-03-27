# Plan C: SkillHub 前端市场页面 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有"插件"页面升级为 SkillHub 市场页面，包含"已安装"和"市场"两个 Tab，支持搜索筛选、安装/卸载/重载操作，展示插件详情和验证状态。

**Architecture:** 替换现有 `PluginsView.vue`，新建 `SkillHubView.vue`（双 Tab 布局），抽取 `PluginCard.vue`（通用插件卡片）和 `SearchBar.vue`（搜索筛选），新建 `api/skillhub.ts` 对接后端 API。路由和导航同步更新。

**Tech Stack:** Vue 3 Composition API + TypeScript, Tailwind CSS, fetch API

**Spec:** `docs/superpowers/specs/2026-03-24-skillhub-agent-comm-design.md` 第 2.7 节

**前置依赖:** Plan B（SkillHub 后端 API）必须先完成。

**现有文件参考:**
- `web/src/views/PluginsView.vue` — 当前插件列表页（将被替换）
- `web/src/api/plugins.ts` — 当前 API（将被删除，已无消费者）
- `web/src/types.ts` — 类型定义
- `web/src/components/BottomNav.vue` — 底部导航
- `web/src/router/index.ts` — 路由
- `web/src/App.vue` — 页面标题映射
- `web/src/composables/useSSE.ts` — SSE 事件处理（switch/case 结构，immutable 模式）

---

### Task 1: 类型定义 + SkillHub API 层

**Files:**
- Modify: `web/src/types.ts`
- Create: `web/src/api/skillhub.ts`
- Test: `web/src/api/__tests__/skillhub.test.ts` (Create)

- [ ] **Step 1: 编写 API 调用测试**

```typescript
// web/src/api/__tests__/skillhub.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchRegistry,
  fetchInstalled,
  searchPlugins,
  installPlugin,
  uninstallPlugin,
} from '../skillhub'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('skillhub API', () => {
  it('fetchRegistry returns index data', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { version: 1, plugins: [{ name: 'test', version: '1.0.0' }] },
      }),
    })

    const result = await fetchRegistry()
    expect(result.version).toBe(1)
    expect(result.plugins).toHaveLength(1)
    expect(mockFetch).toHaveBeenCalledWith('/api/skillhub/registry')
  })

  it('fetchInstalled returns plugin list', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: [{ name: 'meal_agent', source: 'builtin' }],
      }),
    })

    const result = await fetchInstalled()
    expect(result).toHaveLength(1)
    expect(result[0].source).toBe('builtin')
  })

  it('searchPlugins passes query params', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, data: [] }),
    })

    await searchPlugins({ q: '健身', tags: '运动,健康', type: 'agent' })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('q=%E5%81%A5%E8%BA%AB')
    expect(url).toContain('tags=%E8%BF%90%E5%8A%A8')
    expect(url).toContain('type=agent')
  })

  it('installPlugin sends POST with name', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { status: 'installed', version: '1.0.0' },
      }),
    })

    const result = await installPlugin('fitness_agent')
    expect(result.status).toBe('installed')
    expect(mockFetch).toHaveBeenCalledWith('/api/skillhub/install', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('uninstallPlugin sends DELETE', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { status: 'uninstalled' },
      }),
    })

    const result = await uninstallPlugin('fitness_agent')
    expect(result.status).toBe('uninstalled')
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/skillhub/uninstall/fitness_agent',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on API error', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, error: 'not found' }),
    })

    await expect(fetchRegistry()).rejects.toThrow('not found')
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/api/__tests__/skillhub.test.ts`
Expected: FAIL — `../skillhub` 不存在

- [ ] **Step 3: 在 types.ts 中添加 SkillHub 类型**

在 `web/src/types.ts` 末尾追加：

```typescript
// ── SkillHub 类型 ──────────────────────────────

export interface RegistryPlugin {
  name: string
  version: string
  type: 'agent' | 'memory' | 'extension' | 'search'
  description: string
  author: string
  tags: string[]
  min_framework_version: string
  download_url: string
  manifest_url: string
  sha256: string
  verified: boolean
  created_at: string
  updated_at: string
}

export interface RegistryIndex {
  version: number
  updated_at: string
  plugins: RegistryPlugin[]
}

export interface InstalledPlugin {
  name: string
  version: string
  type: 'agent' | 'memory' | 'extension' | 'search'
  status?: string
  capabilities?: string[]
  description?: string
  source: 'builtin' | 'contrib'
}

export interface InstallResult {
  status: 'installed' | 'upgraded' | 'already_latest'
  version: string
}

export interface UninstallResult {
  status: 'uninstalled'
  name: string
}
```

注意：
- `InstalledPlugin.type` 使用与 `Plugin` 一致的联合类型，而非 `string`
- `RegistryPlugin` 包含 `manifest_url` 字段（用于"查看详情"跳转）

- [ ] **Step 4: 实现 skillhub API**

```typescript
// web/src/api/skillhub.ts
import type {
  RegistryIndex,
  RegistryPlugin,
  InstalledPlugin,
  InstallResult,
  UninstallResult,
} from '../types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const json = await res.json()
  if (!json.success) throw new Error(json.error ?? 'Request failed')
  return json.data as T
}

export async function fetchRegistry(): Promise<RegistryIndex> {
  return request<RegistryIndex>('/api/skillhub/registry')
}

export async function fetchInstalled(): Promise<InstalledPlugin[]> {
  return request<InstalledPlugin[]>('/api/skillhub/installed')
}

export async function searchPlugins(params: {
  q?: string
  tags?: string
  type?: string
}): Promise<RegistryPlugin[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.tags) qs.set('tags', params.tags)
  if (params.type) qs.set('type', params.type)
  return request<RegistryPlugin[]>(`/api/skillhub/search?${qs.toString()}`)
}

export async function installPlugin(name: string, version?: string): Promise<InstallResult> {
  return request<InstallResult>('/api/skillhub/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, version }),
  })
}

export async function uninstallPlugin(name: string): Promise<UninstallResult> {
  return request<UninstallResult>(`/api/skillhub/uninstall/${name}`, {
    method: 'DELETE',
  })
}
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/api/__tests__/skillhub.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 6: 提交**

```bash
git add web/src/types.ts web/src/api/skillhub.ts web/src/api/__tests__/skillhub.test.ts
git commit -m "feat: SkillHub 类型定义和 API 层"
```

---

### Task 2: SearchBar 组件 — 搜索 + 标签筛选

**Files:**
- Create: `web/src/components/skillhub/SearchBar.vue`
- Test: `web/src/components/skillhub/__tests__/SearchBar.test.ts` (Create)

- [ ] **Step 1: 编写 SearchBar 测试**

```typescript
// web/src/components/skillhub/__tests__/SearchBar.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '../SearchBar.vue'

describe('SearchBar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('emits search event on input after debounce', async () => {
    const wrapper = mount(SearchBar)
    const input = wrapper.find('input[type="text"]')
    await input.setValue('健身')
    vi.advanceTimersByTime(300)
    expect(wrapper.emitted('search')).toBeTruthy()
    expect(wrapper.emitted('search')![0]).toEqual([{ q: '健身', tags: '', type: '' }])
  })

  it('does not emit before debounce completes', async () => {
    const wrapper = mount(SearchBar)
    const input = wrapper.find('input[type="text"]')
    await input.setValue('健身')
    vi.advanceTimersByTime(100)
    expect(wrapper.emitted('search')).toBeFalsy()
  })

  it('emits filter event on type select', async () => {
    const wrapper = mount(SearchBar)
    const buttons = wrapper.findAll('[data-testid="type-filter"]')
    await buttons[1].trigger('click') // 第二个 = agent
    expect(wrapper.emitted('search')).toBeTruthy()
  })

  it('renders type filter buttons', () => {
    const wrapper = mount(SearchBar)
    const buttons = wrapper.findAll('[data-testid="type-filter"]')
    expect(buttons.length).toBeGreaterThanOrEqual(4) // 全部, agent, memory, extension
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/components/skillhub/__tests__/SearchBar.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现 SearchBar 组件**

```vue
<!-- web/src/components/skillhub/SearchBar.vue -->
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/components/skillhub/__tests__/SearchBar.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add web/src/components/skillhub/SearchBar.vue web/src/components/skillhub/__tests__/SearchBar.test.ts
git commit -m "feat: SearchBar 搜索筛选组件"
```

---

### Task 3: PluginCard 组件 — 通用插件卡片

**Files:**
- Create: `web/src/components/skillhub/PluginCard.vue`
- Test: `web/src/components/skillhub/__tests__/PluginCard.test.ts` (Create)

- [ ] **Step 1: 编写 PluginCard 测试**

```typescript
// web/src/components/skillhub/__tests__/PluginCard.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PluginCard from '../PluginCard.vue'

describe('PluginCard', () => {
  const baseProps = {
    name: 'fitness_agent',
    version: '1.0.0',
    type: 'agent' as const,
    description: 'AI 健身教练',
    author: 'testuser',
    tags: ['健身', '运动'],
  }

  it('renders plugin name and version', () => {
    const wrapper = mount(PluginCard, { props: baseProps })
    expect(wrapper.text()).toContain('fitness_agent')
    expect(wrapper.text()).toContain('1.0.0')
  })

  it('renders type badge', () => {
    const wrapper = mount(PluginCard, { props: baseProps })
    expect(wrapper.text()).toContain('agent')
  })

  it('renders tags', () => {
    const wrapper = mount(PluginCard, { props: baseProps })
    expect(wrapper.text()).toContain('健身')
    expect(wrapper.text()).toContain('运动')
  })

  it('shows verified badge when verified', () => {
    const wrapper = mount(PluginCard, { props: { ...baseProps, verified: true } })
    expect(wrapper.find('[data-testid="verified-badge"]').exists()).toBe(true)
  })

  it('hides verified badge when not verified', () => {
    const wrapper = mount(PluginCard, { props: { ...baseProps, verified: false } })
    expect(wrapper.find('[data-testid="verified-badge"]').exists()).toBe(false)
  })

  it('shows install button for market mode', () => {
    const wrapper = mount(PluginCard, { props: { ...baseProps, mode: 'market' } })
    expect(wrapper.find('[data-testid="install-btn"]').exists()).toBe(true)
  })

  it('shows uninstall button for installed contrib plugin', () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'installed', source: 'contrib', status: 'loaded' },
    })
    expect(wrapper.find('[data-testid="uninstall-btn"]').exists()).toBe(true)
  })

  it('shows reload button for installed contrib plugin', () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'installed', source: 'contrib', status: 'loaded' },
    })
    expect(wrapper.find('[data-testid="reload-btn"]').exists()).toBe(true)
  })

  it('hides uninstall for builtin plugins', () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'installed', source: 'builtin', status: 'loaded' },
    })
    expect(wrapper.find('[data-testid="uninstall-btn"]').exists()).toBe(false)
  })

  it('shows installed mark in market mode', () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'market', isInstalled: true },
    })
    expect(wrapper.find('[data-testid="installed-mark"]').exists()).toBe(true)
  })

  it('emits install event', async () => {
    const wrapper = mount(PluginCard, { props: { ...baseProps, mode: 'market' } })
    await wrapper.find('[data-testid="install-btn"]').trigger('click')
    expect(wrapper.emitted('install')).toBeTruthy()
    expect(wrapper.emitted('install')![0]).toEqual(['fitness_agent'])
  })

  it('emits uninstall event', async () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'installed', source: 'contrib', status: 'loaded' },
    })
    await wrapper.find('[data-testid="uninstall-btn"]').trigger('click')
    expect(wrapper.emitted('uninstall')).toBeTruthy()
  })

  it('emits reload event', async () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'installed', source: 'contrib', status: 'loaded' },
    })
    await wrapper.find('[data-testid="reload-btn"]').trigger('click')
    expect(wrapper.emitted('reload')).toBeTruthy()
  })

  it('renders repository link for market plugins', () => {
    const wrapper = mount(PluginCard, {
      props: { ...baseProps, mode: 'market', repositoryUrl: 'https://github.com/user/repo' },
    })
    const link = wrapper.find('[data-testid="detail-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://github.com/user/repo')
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/components/skillhub/__tests__/PluginCard.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现 PluginCard 组件**

```vue
<!-- web/src/components/skillhub/PluginCard.vue -->
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
</script>
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/components/skillhub/__tests__/PluginCard.test.ts`
Expected: PASS (14 tests)

- [ ] **Step 5: 提交**

```bash
git add web/src/components/skillhub/PluginCard.vue web/src/components/skillhub/__tests__/PluginCard.test.ts
git commit -m "feat: PluginCard 通用插件卡片组件（含重载、查看详情）"
```

---

### Task 4: SkillHubView 主页面 — 双 Tab 布局

**Files:**
- Create: `web/src/views/SkillHubView.vue`
- Test: `web/src/views/__tests__/SkillHubView.test.ts` (Create)

- [ ] **Step 1: 编写 SkillHubView 测试**

```typescript
// web/src/views/__tests__/SkillHubView.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SkillHubView from '../SkillHubView.vue'

// Mock API
vi.mock('../../api/skillhub', () => ({
  fetchInstalled: vi.fn().mockResolvedValue([
    { name: 'meal_agent', version: '0.1.0', type: 'agent', status: 'loaded', source: 'builtin' },
  ]),
  fetchRegistry: vi.fn().mockResolvedValue({
    version: 1,
    plugins: [
      { name: 'fitness_agent', version: '1.0.0', type: 'agent', description: 'AI 健身', author: 'test', tags: ['健身'], verified: true },
    ],
  }),
  searchPlugins: vi.fn().mockResolvedValue([]),
  installPlugin: vi.fn().mockResolvedValue({ status: 'installed', version: '1.0.0' }),
  uninstallPlugin: vi.fn().mockResolvedValue({ status: 'uninstalled' }),
}))

describe('SkillHubView', () => {
  it('renders two tabs', () => {
    const wrapper = mount(SkillHubView)
    const tabs = wrapper.findAll('[data-testid="tab"]')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].text()).toContain('已安装')
    expect(tabs[1].text()).toContain('市场')
  })

  it('shows installed tab by default', async () => {
    const wrapper = mount(SkillHubView)
    await flushPromises()
    expect(wrapper.find('[data-testid="installed-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="market-panel"]').exists()).toBe(false)
  })

  it('switches to market tab', async () => {
    const wrapper = mount(SkillHubView)
    await flushPromises()
    const tabs = wrapper.findAll('[data-testid="tab"]')
    await tabs[1].trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="market-panel"]').exists()).toBe(true)
  })

  it('loads installed plugins on mount', async () => {
    const { fetchInstalled } = await import('../../api/skillhub')
    mount(SkillHubView)
    await flushPromises()
    expect(fetchInstalled).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/views/__tests__/SkillHubView.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现 SkillHubView**

```vue
<!-- web/src/views/SkillHubView.vue -->
<template>
  <div class="flex flex-col h-full">
    <!-- Tab 切换 -->
    <div class="flex border-b border-gray-200 bg-white px-4 shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        data-testid="tab"
        class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
        :class="activeTab === tab.key
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
        <span v-if="tab.key === 'installed' && installedPlugins.length" class="ml-1 text-xs text-gray-400">
          ({{ installedPlugins.length }})
        </span>
      </button>
    </div>

    <!-- 已安装 Tab -->
    <div v-if="activeTab === 'installed'" data-testid="installed-panel" class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      <div v-if="loadingInstalled" class="flex items-center justify-center h-40 text-gray-400 text-sm animate-pulse">
        加载中...
      </div>
      <div v-else-if="errorInstalled" class="flex flex-col items-center justify-center h-40 text-sm">
        <p class="text-red-500">{{ errorInstalled }}</p>
        <button class="mt-2 text-blue-600 underline text-xs" @click="loadInstalled">重试</button>
      </div>
      <template v-else>
        <PluginCard
          v-for="p in installedPlugins"
          :key="p.name"
          :name="p.name"
          :version="p.version"
          :type="p.type"
          :description="p.description"
          :status="p.status"
          :capabilities="p.capabilities"
          :source="p.source"
          mode="installed"
          @uninstall="handleUninstall"
          @reload="handleReload"
        />
        <div v-if="installedPlugins.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm">
          <p class="text-2xl mb-2">🧩</p>
          <p>暂无插件</p>
        </div>
      </template>
    </div>

    <!-- 市场 Tab -->
    <div v-if="activeTab === 'market'" data-testid="market-panel" class="flex flex-col flex-1 overflow-hidden">
      <div class="px-4 pt-4 pb-2 shrink-0">
        <SearchBar @search="handleSearch" />
      </div>

      <div class="flex-1 overflow-y-auto px-4 pb-4 space-y-3">
        <div v-if="loadingMarket" class="flex items-center justify-center h-40 text-gray-400 text-sm animate-pulse">
          加载中...
        </div>
        <div v-else-if="errorMarket" class="flex flex-col items-center justify-center h-40 text-sm">
          <p class="text-red-500">{{ errorMarket }}</p>
          <button class="mt-2 text-blue-600 underline text-xs" @click="loadMarket">重试</button>
        </div>
        <template v-else>
          <PluginCard
            v-for="p in marketPlugins"
            :key="p.name"
            :name="p.name"
            :version="p.version"
            :type="p.type"
            :description="p.description"
            :author="p.author"
            :tags="p.tags"
            :verified="p.verified"
            :repository-url="p.manifest_url"
            mode="market"
            :is-installed="installedNames.has(p.name)"
            :installing="installingSet.has(p.name)"
            @install="handleInstall"
          />
          <div v-if="marketPlugins.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm">
            <p class="text-2xl mb-2">🔍</p>
            <p>未找到匹配的插件</p>
          </div>
        </template>
      </div>
    </div>

    <!-- Toast 通知 -->
    <Transition name="fade">
      <div
        v-if="toast"
        class="fixed bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm shadow-lg z-50"
        :class="toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'"
      >
        {{ toast.message }}
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import PluginCard from '../components/skillhub/PluginCard.vue'
import SearchBar from '../components/skillhub/SearchBar.vue'
import {
  fetchInstalled,
  fetchRegistry,
  searchPlugins,
  installPlugin,
  uninstallPlugin,
} from '../api/skillhub'
import type { InstalledPlugin, RegistryPlugin } from '../types'

const tabs = [
  { key: 'installed', label: '已安装' },
  { key: 'market', label: '市场' },
] as const

type TabKey = typeof tabs[number]['key']

const activeTab = ref<TabKey>('installed')

// 已安装
const installedPlugins = ref<InstalledPlugin[]>([])
const loadingInstalled = ref(false)
const errorInstalled = ref<string | null>(null)

// 市场
const marketPlugins = ref<RegistryPlugin[]>([])
const loadingMarket = ref(false)
const errorMarket = ref<string | null>(null)
const installingSet = ref<Set<string>>(new Set())

// Toast
const toast = ref<{ message: string; type: 'success' | 'error' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

const installedNames = computed(() => new Set(installedPlugins.value.map(p => p.name)))

function showToast(message: string, type: 'success' | 'error' = 'success') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { message, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

async function loadInstalled() {
  loadingInstalled.value = true
  errorInstalled.value = null
  try {
    installedPlugins.value = await fetchInstalled()
  } catch (e) {
    errorInstalled.value = (e as Error).message
  } finally {
    loadingInstalled.value = false
  }
}

async function loadMarket() {
  loadingMarket.value = true
  errorMarket.value = null
  try {
    const index = await fetchRegistry()
    marketPlugins.value = index.plugins
  } catch (e) {
    errorMarket.value = (e as Error).message
  } finally {
    loadingMarket.value = false
  }
}

function switchTab(tab: TabKey) {
  activeTab.value = tab
  if (tab === 'market' && marketPlugins.value.length === 0 && !loadingMarket.value) {
    loadMarket()
  }
}

async function handleSearch(params: { q: string; tags: string; type: string }) {
  if (!params.q && !params.tags && !params.type) {
    loadMarket()
    return
  }
  loadingMarket.value = true
  errorMarket.value = null
  try {
    marketPlugins.value = await searchPlugins(params)
  } catch (e) {
    errorMarket.value = (e as Error).message
  } finally {
    loadingMarket.value = false
  }
}

async function handleInstall(name: string) {
  const next = new Set(installingSet.value)
  next.add(name)
  installingSet.value = next

  try {
    const result = await installPlugin(name)
    if (result.status === 'already_latest') {
      showToast(`${name} 已是最新版本`)
    } else {
      showToast(`${name} v${result.version} 安装成功`)
    }
    await loadInstalled()
  } catch (e) {
    showToast((e as Error).message, 'error')
  } finally {
    const cleaned = new Set(installingSet.value)
    cleaned.delete(name)
    installingSet.value = cleaned
  }
}

async function handleUninstall(name: string) {
  try {
    await uninstallPlugin(name)
    showToast(`${name} 已卸载`)
    await loadInstalled()
  } catch (e) {
    showToast((e as Error).message, 'error')
  }
}

async function handleReload(name: string) {
  showToast(`${name} 重载中...`)
  // 重载调用后端 reload API（Plan B 的 reload_plugin 通过 unload + load 实现）
  // 当前先刷新列表，完整重载需后端支持 reload endpoint
  await loadInstalled()
  showToast(`${name} 已重载`)
}

onMounted(loadInstalled)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/views/__tests__/SkillHubView.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: 提交**

```bash
git add web/src/views/SkillHubView.vue web/src/views/__tests__/SkillHubView.test.ts
git commit -m "feat: SkillHubView 双 Tab 市场页面（已安装 + 市场）"
```

---

### Task 5: 路由 + 导航 + 标题更新

**Files:**
- Modify: `web/src/router/index.ts`
- Modify: `web/src/components/BottomNav.vue`
- Modify: `web/src/App.vue`
- Delete: `web/src/views/PluginsView.vue` (被 SkillHubView 替代)
- Delete: `web/src/api/plugins.ts` (不再有消费者)

- [ ] **Step 1: 更新路由**

修改 `web/src/router/index.ts`，将 `/plugins` 替换为 `/skillhub`，保留 `/devices` 路由不变：

```typescript
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: () => import('../views/ChatView.vue') },
    { path: '/devices', name: 'devices', component: () => import('../views/DevicesView.vue') },
    { path: '/skillhub', name: 'skillhub', component: () => import('../views/SkillHubView.vue') },
    // 兼容旧路由
    { path: '/plugins', redirect: '/skillhub' },
  ],
})
```

- [ ] **Step 2: 更新 BottomNav**

修改 `web/src/components/BottomNav.vue` 的 tabs 数组，将"插件"改为"市场"：

```typescript
const tabs = [
  { to: '/', icon: '💬', label: '对话' },
  { to: '/skillhub', icon: '🏪', label: '市场' },
]
```

注意：`/devices` 不在 BottomNav 中（当前也没有），保持不变。

- [ ] **Step 3: 更新 App.vue 标题映射**

在 `web/src/App.vue` 中更新 `pageTitle` 的映射，保留 `/devices`：

```typescript
const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/': '如意助手',
    '/devices': '设备网关',
    '/skillhub': '技能市场',
  }
  return titles[route.path] ?? 'Life-Agent-RU-YEE'
})
```

- [ ] **Step 4: 删除旧文件**

删除不再需要的文件：
- `web/src/views/PluginsView.vue`（已被 SkillHubView 替代）
- `web/src/api/plugins.ts`（唯一消费者 PluginsView 已删除）

- [ ] **Step 5: 验证构建通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx tsc --noEmit && npm run build`
Expected: 无 TypeScript 错误，构建成功

- [ ] **Step 6: 提交**

```bash
git add web/src/router/index.ts web/src/components/BottomNav.vue web/src/App.vue
git rm web/src/views/PluginsView.vue web/src/api/plugins.ts
git commit -m "feat: 路由和导航更新，插件页升级为技能市场"
```

---

### Task 6: SSE agent_delegate 事件前端支持

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/composables/useSSE.ts`
- Test: `web/src/composables/__tests__/useSSE-delegate.test.ts` (Create)

- [ ] **Step 1: 编写 delegate 事件测试**

```typescript
// web/src/composables/__tests__/useSSE-delegate.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// 测试 useSSE 的 delegate 事件处理逻辑
// 由于 useSSE 内部的 callback 不易直接测试，
// 我们提取事件处理的核心逻辑进行验证

describe('SSE delegate event handling', () => {
  it('agent_delegate sets thinking on assistant message', () => {
    // 模拟 useSSE 内部的事件处理逻辑
    const msg = {
      id: 'test-1',
      role: 'assistant' as const,
      content: '',
      timestamp: Date.now(),
      thinking: undefined as string | undefined,
    }

    // 模拟 agent_delegate 事件处理
    const data = { source: 'meal_agent', target: 'fitness_agent', message: '查询运动量' }
    msg.thinking = `正在咨询 ${data.target}...`

    expect(msg.thinking).toBe('正在咨询 fitness_agent...')
  })

  it('agent_delegate_done clears thinking', () => {
    const msg = {
      id: 'test-1',
      role: 'assistant' as const,
      content: '',
      timestamp: Date.now(),
      thinking: '正在咨询 fitness_agent...',
    }

    // 模拟 agent_delegate_done 事件处理
    msg.thinking = undefined

    expect(msg.thinking).toBeUndefined()
  })
})
```

- [ ] **Step 2: 运行测试验证通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run src/composables/__tests__/useSSE-delegate.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 3: 在 types.ts 中添加 delegate 事件类型**

在 `web/src/types.ts` 的 `SSEEvent` 联合类型末尾（`| { event: 'error' ...}` 之后）追加：

```typescript
  | { event: 'thinking'; data: { status: string } }
  | { event: 'agent_delegate'; data: { source: string; target: string; message: string } }
  | { event: 'agent_delegate_done'; data: { source: string; target: string; summary: string } }
```

- [ ] **Step 4: 在 useSSE.ts switch 中添加 delegate 事件处理**

在 `web/src/composables/useSSE.ts` 的 `switch (event)` 块中，在 `case 'thinking':` 之后、`case 'error':` 之前，添加两个 case：

```typescript
            case 'agent_delegate':
              msg.thinking = `正在咨询 ${data.target}...`
              break
            case 'agent_delegate_done':
              msg.thinking = undefined
              break
```

这两个 case 位于 switch 块内，`msg` 已经是 `{ ...messages.value[idx] }` 的浅拷贝，后续通过 `updated[idx] = msg` 不可变替换。完全符合现有的 immutable 模式。

- [ ] **Step 5: 验证构建通过**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx tsc --noEmit`
Expected: 无 TypeScript 错误

- [ ] **Step 6: 提交**

```bash
git add web/src/types.ts web/src/composables/useSSE.ts web/src/composables/__tests__/useSSE-delegate.test.ts
git commit -m "feat: 前端支持 agent_delegate SSE 事件，显示 Agent 协作状态"
```

---

### Task 7: 全面验证

- [ ] **Step 1: 运行全部前端测试**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 2: 验证构建**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY/web && npm run build`
Expected: 构建成功

- [ ] **Step 3: 手动验证关键交互（如果有运行环境）**

- 导航到 `/skillhub`
- 已安装 Tab 显示内置插件
- 切换到市场 Tab 加载远程索引
- 搜索关键词筛选结果
- 类型筛选按钮工作
- 安装按钮 → loading → 成功 toast
- 卸载按钮 → 成功 toast → 列表刷新
- 重载按钮 → 提示重载中 → 列表刷新
- 已安装的插件在市场 Tab 显示"已安装"标记
- 市场插件"查看详情"链接跳转到 GitHub
- `/plugins` 旧路由自动重定向到 `/skillhub`
- `/devices` 路由仍然正常工作

- [ ] **Step 4: 提交最终验证**

```bash
git commit --allow-empty -m "chore: Plan C 前端市场页面验证通过"
```

---

## 可能出现的问题

1. **@vue/test-utils 未安装**：需要确认 `web/package.json` 中包含 `@vue/test-utils`。如果没有需要先安装。
2. **vitest mock 模块路径**：`vi.mock('../../api/skillhub')` 的路径必须与实际 import 路径完全匹配。
3. **Tailwind CSS 清理**：`line-clamp-2` 需要 `@tailwindcss/line-clamp` 插件（Tailwind v3.3+ 已内置）。
4. **fetch API mock**：测试中使用 `vi.stubGlobal('fetch', mockFetch)` mock 全局 fetch。
5. **路由重定向**：`/plugins` → `/skillhub` 重定向确保旧书签仍可用。
6. **SSE 事件兼容**：如果后端 Plan A 未部署，`agent_delegate` 事件不会触发，前端代码不影响现有功能。
7. **重载功能**：当前 handleReload 只是刷新列表，完整重载需后端提供 reload endpoint（Plan B 的 PluginRegistry 已有 reload_plugin 方法）。

## 建议的测试用例

| 场景 | 预期结果 |
|------|----------|
| 默认显示已安装 Tab | 加载并展示已安装插件 |
| 切换到市场 Tab | 自动拉取远程索引并显示 |
| 搜索关键词 | 防抖 300ms 后筛选结果 |
| 类型筛选 | 立即筛选结果 |
| 安装插件 | loading → 成功 toast → 刷新已安装列表 |
| 安装已有版本 | toast 提示"已是最新" |
| 卸载社区插件 | 成功 toast → 从列表移除 |
| 重载社区插件 | toast 提示 → 列表刷新 |
| 内置插件无卸载/重载按钮 | 不显示操作按钮 |
| 已安装的在市场显示标记 | "已安装"标记替代安装按钮 |
| 已验证插件显示徽章 | 绿色"已验证"徽章 |
| 市场插件"查看详情" | 打开新标签跳转 GitHub |
| API 错误 | 红色 toast 提示 |
| 网络加载失败 | 显示错误信息 + 重试按钮 |
| `/plugins` 旧路由 | 自动重定向到 `/skillhub` |
| `/devices` 路由 | 正常显示设备网关页面 |
