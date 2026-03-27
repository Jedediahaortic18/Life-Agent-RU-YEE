# Frontend Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first Vue 3 SPA that showcases Life-Agent-RU-YEE's SSE streaming chat, device gateway WebSocket, and plugin system.

**Architecture:** Single SPA with Vue Router (3 pages: Chat, Devices, Plugins). Composables handle SSE/WebSocket connections. nginx serves static files and reverse-proxies API requests. All code lives in `web/` directory.

**Tech Stack:** Vue 3, Vite, TailwindCSS, TypeScript, Vue Router, marked, Vitest

**Spec:** `docs/superpowers/specs/2026-03-23-frontend-demo-design.md`

**Deployment:** Remote server `ssh root@218.244.148.190`, project at `/root/workspace/Life-Agent-RU-YEE/`

---

## File Map

| File | Responsibility |
|------|----------------|
| `web/package.json` | Dependencies and scripts |
| `web/index.html` | HTML entry point |
| `web/vite.config.ts` | Vite config with API proxy |
| `web/tailwind.config.js` | TailwindCSS config (mobile-first) |
| `web/postcss.config.js` | PostCSS with Tailwind plugin |
| `web/tsconfig.json` | TypeScript config |
| `web/src/main.ts` | App entry, mount router |
| `web/src/App.vue` | Root layout + BottomNav |
| `web/src/router/index.ts` | Route definitions |
| `web/src/types.ts` | Shared TypeScript interfaces |
| `web/src/api/health.ts` | GET /api/health |
| `web/src/api/chat.ts` | POST /api/chat SSE stream |
| `web/src/api/plugins.ts` | GET /api/plugins |
| `web/src/api/devices.ts` | WebSocket /api/devices/ws |
| `web/src/composables/useSSE.ts` | SSE event stream parser + chat state management |
| `web/src/composables/useWebSocket.ts` | WebSocket with reconnect |
| `web/src/components/AppHeader.vue` | Top bar with status |
| `web/src/components/BottomNav.vue` | Mobile bottom tab navigation |
| `web/src/components/chat/MessageBubble.vue` | User/assistant message bubble |
| `web/src/components/chat/ToolCallCard.vue` | Tool call display card |
| `web/src/components/chat/StreamingText.vue` | Streaming text with cursor |
| `web/src/components/devices/DeviceCard.vue` | Device status card |
| `web/src/views/ChatView.vue` | Chat page |
| `web/src/views/DevicesView.vue` | Devices page |
| `web/src/views/PluginsView.vue` | Plugins page |
| `web/src/styles/main.css` | Tailwind entry |
| `nginx.conf` | nginx reverse proxy config |
| `docker-compose.yml` | Add nginx service (modify) |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/vite.config.ts`
- Create: `web/tailwind.config.js`
- Create: `web/postcss.config.js`
- Create: `web/tsconfig.json`
- Create: `web/src/main.ts`
- Create: `web/src/styles/main.css`
- Create: `web/src/App.vue`

- [ ] **Step 1: Create web directory and package.json**

```bash
ssh root@218.244.148.190 "mkdir -p /root/workspace/Life-Agent-RU-YEE/web/src/{api,composables,components/{chat,devices},views,router,styles}"
```

```json
// web/package.json
{
  "name": "lary-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:ui": "vitest --ui"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "marked": "^15.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.2.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^2.1.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^25.0.0"
  }
}
```

- [ ] **Step 2: Create vite.config.ts with API proxy**

```typescript
// web/vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 3: Create TailwindCSS config files**

```javascript
// web/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

```javascript
// web/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 4: Create TypeScript config**

```json
// web/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

```json
// web/tsconfig.node.json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create index.html, main.ts, main.css, and minimal App.vue**

```html
<!-- web/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Life-Agent-RU-YEE</title>
</head>
<body class="bg-gray-50">
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

```css
/* web/src/styles/main.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

```typescript
// web/src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles/main.css'

createApp(App).use(router).mount('#app')
```

```vue
<!-- web/src/App.vue -->
<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <router-view />
  </div>
</template>

<script setup lang="ts">
</script>
```

- [ ] **Step 6: Install dependencies and verify dev server starts**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npm install"
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vite --host 0.0.0.0 &; sleep 5 && curl -s http://localhost:5173 | head -20 && kill %1"
```

Expected: HTML output containing `<div id="app">`.

- [ ] **Step 7: Commit**

```bash
cd /root/workspace/Life-Agent-RU-YEE
git add web/
git commit -m "feat: 前端项目脚手架 - Vue 3 + Vite + TailwindCSS"
```

---

### Task 2: TypeScript Types + Router + Shell Layout

**Files:**
- Create: `web/src/types.ts`
- Create: `web/src/router/index.ts`
- Create: `web/src/components/AppHeader.vue`
- Create: `web/src/components/BottomNav.vue`
- Modify: `web/src/App.vue`
- Create: `web/src/views/ChatView.vue` (placeholder)
- Create: `web/src/views/DevicesView.vue` (placeholder)
- Create: `web/src/views/PluginsView.vue` (placeholder)

- [ ] **Step 1: Create shared types**

```typescript
// web/src/types.ts
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  toolCalls?: ToolCallInfo[]
}

export interface ToolCallInfo {
  tool: string
  params: Record<string, any>
  result?: { success: boolean; data: any; error: string | null }
  collapsed: boolean
}

export type SSEEvent =
  | { event: 'text_delta'; data: { content: string } }
  | { event: 'tool_call'; data: { tool: string; params: Record<string, any> } }
  | { event: 'tool_output'; data: { tool: string; result: { success: boolean; data: any; error: string | null } } }
  | { event: 'tool_error'; data: { tool: string; error: string } }
  | { event: 'done'; data: { session_id: string; agent: string } }
  | { event: 'error'; data: { error: string; suggestion?: string } }

export interface Plugin {
  name: string
  type: 'agent' | 'memory' | 'search' | 'extension'
  version: string
  status: 'loaded' | 'unloaded'
  capabilities: string[]
}

export interface Device {
  device_id: string
  name: string
  device_type: string
  status: 'online' | 'offline'
  last_heartbeat: string
  capabilities: string[]
}

export interface MessageEnvelope {
  id: string
  type: 'chat' | 'heartbeat' | 'device_command' | 'device_result' | 'device_register' | 'device_registered' | 'error'
  device_id: string | null
  payload: Record<string, any>
  timestamp: string
  ack_required: boolean
}
```

- [ ] **Step 2: Create router**

```typescript
// web/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: () => import('../views/ChatView.vue') },
    { path: '/devices', name: 'devices', component: () => import('../views/DevicesView.vue') },
    { path: '/plugins', name: 'plugins', component: () => import('../views/PluginsView.vue') },
  ],
})
```

- [ ] **Step 3: Create AppHeader component**

```vue
<!-- web/src/components/AppHeader.vue -->
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
```

- [ ] **Step 4: Create BottomNav component**

```vue
<!-- web/src/components/BottomNav.vue -->
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
  { to: '/devices', icon: '📱', label: '设备' },
  { to: '/plugins', icon: '🧩', label: '插件' },
]
</script>
```

- [ ] **Step 5: Create placeholder views**

```vue
<!-- web/src/views/ChatView.vue -->
<template>
  <div class="flex-1 flex items-center justify-center text-gray-400">
    聊天页面 - 待实现
  </div>
</template>
```

```vue
<!-- web/src/views/DevicesView.vue -->
<template>
  <div class="flex-1 flex items-center justify-center text-gray-400">
    设备页面 - 待实现
  </div>
</template>
```

```vue
<!-- web/src/views/PluginsView.vue -->
<template>
  <div class="flex-1 flex items-center justify-center text-gray-400">
    插件页面 - 待实现
  </div>
</template>
```

- [ ] **Step 6: Update App.vue with AppHeader + BottomNav**

```vue
<!-- web/src/App.vue -->
<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <AppHeader :title="pageTitle" :online="isOnline" />
    <router-view class="flex-1 overflow-hidden" />
    <BottomNav />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import BottomNav from './components/BottomNav.vue'
import { checkHealth } from './api/health'

const route = useRoute()
const isOnline = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/': '如意助手',
    '/devices': '设备网关',
    '/plugins': '插件列表',
  }
  return titles[route.path] ?? 'Life-Agent-RU-YEE'
})

async function pollHealth() {
  isOnline.value = await checkHealth()
}

onMounted(() => {
  pollHealth()
  healthTimer = setInterval(pollHealth, 10_000)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
})
</script>
```

- [ ] **Step 7: Verify app renders with navigation**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vite --host 0.0.0.0 &; sleep 5 && curl -s http://localhost:5173 | head -30 && kill %1"
```

Expected: HTML with app div, no errors in console.

- [ ] **Step 8: Commit**

```bash
git add web/src/
git commit -m "feat: 添加类型定义、路由、顶部栏和底部导航"
```

---

### Task 3: API Layer + SSE Composable

**Files:**
- Create: `web/src/api/health.ts`
- Create: `web/src/api/chat.ts`
- Create: `web/src/api/plugins.ts`
- Create: `web/src/api/devices.ts`
- Create: `web/src/composables/useSSE.ts`

- [ ] **Step 1: Create API modules**

```typescript
// web/src/api/health.ts
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    return data.status === 'ok'
  } catch {
    return false
  }
}
```

```typescript
// web/src/api/chat.ts
export function streamChat(
  message: string,
  sessionId?: string,
  onEvent?: (event: string, data: any) => void,
  signal?: AbortSignal
): Promise<void> {
  return new Promise(async (resolve, reject) => {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
        signal,
      })

      if (!res.ok) {
        reject(new Error(`HTTP ${res.status}`))
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        reject(new Error('No readable stream'))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        let currentEvent = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              onEvent?.(currentEvent, data)
            } catch { /* ignore parse errors */ }
            currentEvent = ''
          }
        }
      }

      resolve()
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        resolve()
      } else {
        reject(err)
      }
    }
  })
}
```

```typescript
// web/src/api/plugins.ts
import type { Plugin } from '../types'

export async function fetchPlugins(): Promise<Plugin[]> {
  const res = await fetch('/api/plugins')
  const data = await res.json()
  if (!data.success) throw new Error(data.error ?? 'Failed to fetch plugins')
  return data.data as Plugin[]
}
```

```typescript
// web/src/api/devices.ts
import type { MessageEnvelope } from '../types'

export function createDeviceSocket(
  onMessage: (envelope: MessageEnvelope) => void,
  onStateChange: (connected: boolean) => void
): { send: (msg: Partial<MessageEnvelope>) => void; close: () => void } {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/api/devices/ws`

  let ws: WebSocket | null = null
  let retries = 0
  const maxRetries = 5
  let closed = false

  function connect() {
    ws = new WebSocket(url)

    ws.onopen = () => {
      retries = 0
      onStateChange(true)
    }

    ws.onmessage = (e) => {
      try {
        const envelope = JSON.parse(e.data) as MessageEnvelope
        onMessage(envelope)
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      onStateChange(false)
      if (!closed && retries < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retries), 30000)
        retries++
        setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  connect()

  return {
    send(msg: Partial<MessageEnvelope>) {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg))
      }
    },
    close() {
      closed = true
      ws?.close()
    },
  }
}
```

- [ ] **Step 2: Create useSSE composable**

```typescript
// web/src/composables/useSSE.ts
import { ref } from 'vue'
import { streamChat } from '../api/chat'
import type { Message, ToolCallInfo } from '../types'

function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

export function useSSE() {
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  let abortCtrl: AbortController | null = null

  async function send(text: string) {
    if (isStreaming.value || !text.trim()) return

    error.value = null
    isStreaming.value = true

    // user message
    messages.value = [
      ...messages.value,
      { id: uid(), role: 'user', content: text, timestamp: Date.now() },
    ]

    // assistant placeholder
    const assistantId = uid()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      toolCalls: [],
    }
    messages.value = [...messages.value, assistantMsg]

    abortCtrl = new AbortController()

    try {
      await streamChat(
        text,
        undefined,
        (event, data) => {
          const idx = messages.value.findIndex((m) => m.id === assistantId)
          if (idx === -1) return
          const msg = { ...messages.value[idx] }

          switch (event) {
            case 'text_delta':
              msg.content += data.content ?? ''
              break
            case 'tool_call': {
              const tc: ToolCallInfo = {
                tool: data.tool,
                params: data.params,
                collapsed: true,
              }
              msg.toolCalls = [...(msg.toolCalls ?? []), tc]
              break
            }
            case 'tool_output': {
              const calls = [...(msg.toolCalls ?? [])]
              const tcIdx = calls.findLastIndex((c) => c.tool === data.tool)
              if (tcIdx !== -1) {
                calls[tcIdx] = { ...calls[tcIdx], result: data.result }
              }
              msg.toolCalls = calls
              break
            }
            case 'tool_error': {
              const calls2 = [...(msg.toolCalls ?? [])]
              const teIdx = calls2.findLastIndex((c) => c.tool === data.tool)
              if (teIdx !== -1) {
                calls2[teIdx] = {
                  ...calls2[teIdx],
                  result: { success: false, data: null, error: data.error },
                }
              }
              msg.toolCalls = calls2
              break
            }
            case 'error':
              error.value = data.error
              break
            case 'done':
              break
          }

          const updated = [...messages.value]
          updated[idx] = msg
          messages.value = updated
        },
        abortCtrl.signal
      )
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      isStreaming.value = false
      abortCtrl = null
    }
  }

  function stop() {
    abortCtrl?.abort()
  }

  function clear() {
    messages.value = []
    error.value = null
  }

  return { messages, isStreaming, error, send, stop, clear }
}
```

- [ ] **Step 3: Verify TypeScript compilation**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vue-tsc --noEmit 2>&1 | tail -20"
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/api/ web/src/composables/
git commit -m "feat: 添加 API 层和 SSE composable"
```

---

### Task 4: Chat Page Components

**Files:**
- Create: `web/src/components/chat/StreamingText.vue`
- Create: `web/src/components/chat/ToolCallCard.vue`
- Create: `web/src/components/chat/MessageBubble.vue`

- [ ] **Step 1: Create StreamingText component**

```vue
<!-- web/src/components/chat/StreamingText.vue -->
<template>
  <span>
    <span v-html="rendered" />
    <span v-if="streaming" class="inline-block w-1.5 h-4 bg-gray-600 animate-pulse ml-0.5 align-text-bottom" />
  </span>
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
```

- [ ] **Step 2: Create ToolCallCard component**

```vue
<!-- web/src/components/chat/ToolCallCard.vue -->
<template>
  <div class="my-2 rounded-lg border border-gray-200 bg-gray-50 text-sm overflow-hidden">
    <button
      class="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-gray-100 transition"
      @click="$emit('toggle')"
    >
      <span class="text-base">🔧</span>
      <span class="font-medium text-gray-700 flex-1">{{ info.tool }}</span>
      <span v-if="info.result" class="text-xs" :class="info.result.success ? 'text-green-600' : 'text-red-500'">
        {{ info.result.success ? '完成' : '失败' }}
      </span>
      <span v-else class="text-xs text-yellow-600 animate-pulse">执行中...</span>
      <span class="text-gray-400 text-xs">{{ info.collapsed ? '▶' : '▼' }}</span>
    </button>
    <div v-if="!info.collapsed" class="px-3 pb-3 space-y-2">
      <div>
        <div class="text-xs text-gray-500 mb-1">参数</div>
        <pre class="text-xs bg-white rounded p-2 overflow-x-auto">{{ JSON.stringify(info.params, null, 2) }}</pre>
      </div>
      <div v-if="info.result">
        <div class="text-xs text-gray-500 mb-1">结果</div>
        <pre class="text-xs bg-white rounded p-2 overflow-x-auto max-h-48 overflow-y-auto">{{ JSON.stringify(info.result, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolCallInfo } from '../../types'

defineProps<{ info: ToolCallInfo }>()
defineEmits<{ toggle: [] }>()
</script>
```

- [ ] **Step 3: Create MessageBubble component**

```vue
<!-- web/src/components/chat/MessageBubble.vue -->
<template>
  <div class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
    <div
      class="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
      :class="msg.role === 'user'
        ? 'bg-blue-600 text-white rounded-br-md'
        : 'bg-white text-gray-800 border border-gray-200 rounded-bl-md'"
    >
      <template v-if="msg.role === 'assistant'">
        <StreamingText
          v-if="msg.content"
          :content="msg.content"
          :streaming="streaming && !msg.toolCalls?.length"
        />
        <ToolCallCard
          v-for="(tc, i) in msg.toolCalls"
          :key="i"
          :info="tc"
          @toggle="$emit('toggleTool', i)"
        />
        <div v-if="streaming && !msg.content && !msg.toolCalls?.length"
          class="flex gap-1 py-1">
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.15s]" />
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.3s]" />
        </div>
      </template>
      <template v-else>
        {{ msg.content }}
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '../../types'
import StreamingText from './StreamingText.vue'
import ToolCallCard from './ToolCallCard.vue'

defineProps<{ msg: Message; streaming?: boolean }>()
defineEmits<{ toggleTool: [index: number] }>()
</script>
```

- [ ] **Step 4: Verify TypeScript compilation**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vue-tsc --noEmit 2>&1 | tail -20"
```

- [ ] **Step 5: Commit**

```bash
git add web/src/components/chat/
git commit -m "feat: 添加聊天组件 - MessageBubble, ToolCallCard, StreamingText"
```

---

### Task 5: Chat View (Full Page)

**Files:**
- Modify: `web/src/views/ChatView.vue`

- [ ] **Step 1: Implement ChatView**

```vue
<!-- web/src/views/ChatView.vue -->
<template>
  <div class="flex flex-col h-full">
    <!-- Error toast -->
    <div
      v-if="error"
      class="mx-4 mt-2 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between"
    >
      <span>{{ error }}</span>
      <button class="text-red-500 underline text-xs ml-2" @click="retryLast">重试</button>
    </div>

    <!-- Messages -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 text-sm">
        <p class="text-2xl mb-2">🍽️</p>
        <p>向如意助手提问吧</p>
        <p class="text-xs mt-1">试试「帮我推荐3道低卡午餐」</p>
      </div>
      <MessageBubble
        v-for="(msg, i) in messages"
        :key="msg.id"
        :msg="msg"
        :streaming="isStreaming && i === messages.length - 1 && msg.role === 'assistant'"
        @toggle-tool="toggleTool(msg.id, $event)"
      />
      <div ref="scrollAnchor" />
    </div>

    <!-- Input -->
    <div class="border-t border-gray-200 bg-white px-4 py-3">
      <form class="flex gap-2" @submit.prevent="handleSend">
        <input
          ref="inputEl"
          v-model="input"
          type="text"
          placeholder="输入消息..."
          class="flex-1 rounded-full border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          :disabled="isStreaming"
        />
        <button
          type="submit"
          class="shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center disabled:opacity-40"
          :disabled="isStreaming || !input.trim()"
        >
          <span class="text-lg">↑</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useSSE } from '../composables/useSSE'
import MessageBubble from '../components/chat/MessageBubble.vue'

const { messages, isStreaming, error, send, clear } = useSSE()

const input = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const scrollAnchor = ref<HTMLElement | null>(null)
let lastInput = ''

function handleSend() {
  const text = input.value.trim()
  if (!text || isStreaming.value) return
  lastInput = text
  input.value = ''
  send(text)
}

function retryLast() {
  if (lastInput) {
    error.value = null
    send(lastInput)
  }
}

function toggleTool(msgId: string, toolIdx: number) {
  const idx = messages.value.findIndex((m) => m.id === msgId)
  if (idx === -1) return
  const msg = { ...messages.value[idx] }
  const calls = [...(msg.toolCalls ?? [])]
  calls[toolIdx] = { ...calls[toolIdx], collapsed: !calls[toolIdx].collapsed }
  msg.toolCalls = calls
  const updated = [...messages.value]
  updated[idx] = msg
  messages.value = updated
}

// auto scroll
watch(
  () => messages.value.length + (messages.value.at(-1)?.content.length ?? 0),
  () => {
    nextTick(() => {
      scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' })
    })
  }
)
</script>
```

- [ ] **Step 2: Verify app compiles and chat page renders**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vue-tsc --noEmit 2>&1 | tail -10"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/views/ChatView.vue
git commit -m "feat: 实现聊天页面 - SSE 流式对话 + Tool 调用展示"
```

---

### Task 6: Devices Page

**Files:**
- Create: `web/src/composables/useWebSocket.ts`
- Create: `web/src/components/devices/DeviceCard.vue`
- Modify: `web/src/views/DevicesView.vue`

- [ ] **Step 1: Create useWebSocket composable**

```typescript
// web/src/composables/useWebSocket.ts
import { ref, onUnmounted } from 'vue'
import { createDeviceSocket } from '../api/devices'
import type { Device, MessageEnvelope } from '../types'

export function useWebSocket() {
  const devices = ref<Device[]>([])
  const connected = ref(false)
  const deviceMessages = ref<MessageEnvelope[]>([])

  const socket = createDeviceSocket(
    (envelope) => {
      switch (envelope.type) {
        case 'device_registered': {
          const existing = devices.value.find((d) => d.device_id === envelope.device_id)
          if (!existing) {
            devices.value = [
              ...devices.value,
              {
                device_id: envelope.device_id ?? '',
                name: envelope.payload.name ?? 'Unknown',
                device_type: envelope.payload.device_type ?? 'unknown',
                status: 'online',
                last_heartbeat: envelope.timestamp,
                capabilities: envelope.payload.capabilities ?? [],
              },
            ]
          }
          break
        }
        case 'heartbeat': {
          devices.value = devices.value.map((d) =>
            d.device_id === envelope.device_id
              ? { ...d, status: envelope.payload.status ?? 'online', last_heartbeat: envelope.timestamp }
              : d
          )
          break
        }
        case 'device_result':
        case 'chat':
        case 'error':
          deviceMessages.value = [...deviceMessages.value, envelope]
          break
      }
    },
    (state) => {
      connected.value = state
    }
  )

  function sendCommand(deviceId: string, action: string, data: string) {
    socket.send({
      type: 'device_command',
      device_id: deviceId,
      payload: { action, data },
    })
  }

  onUnmounted(() => {
    socket.close()
  })

  return { devices, connected, deviceMessages, sendCommand }
}
```

- [ ] **Step 2: Create DeviceCard component**

```vue
<!-- web/src/components/devices/DeviceCard.vue -->
<template>
  <div
    class="rounded-lg border bg-white p-4 cursor-pointer transition hover:shadow-sm"
    :class="device.status === 'online' ? 'border-green-200' : 'border-gray-200'"
    @click="$emit('select', device)"
  >
    <div class="flex items-center gap-3">
      <span
        class="w-3 h-3 rounded-full shrink-0"
        :class="device.status === 'online' ? 'bg-green-500' : 'bg-gray-300'"
      />
      <div class="flex-1 min-w-0">
        <div class="font-medium text-sm text-gray-900 truncate">{{ device.name }}</div>
        <div class="text-xs text-gray-500">{{ device.device_type }}</div>
      </div>
      <div class="text-xs text-gray-400">
        {{ formatTime(device.last_heartbeat) }}
      </div>
    </div>
    <div v-if="expanded" class="mt-3 pt-3 border-t border-gray-100 text-xs space-y-1">
      <div class="text-gray-500">ID: <span class="text-gray-700 font-mono">{{ device.device_id }}</span></div>
      <div v-if="device.capabilities.length" class="flex flex-wrap gap-1 mt-1">
        <span
          v-for="cap in device.capabilities"
          :key="cap"
          class="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full"
        >
          {{ cap }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Device } from '../../types'

defineProps<{ device: Device; expanded?: boolean }>()
defineEmits<{ select: [device: Device] }>()

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>
```

- [ ] **Step 3: Implement DevicesView**

```vue
<!-- web/src/views/DevicesView.vue -->
<template>
  <div class="flex flex-col h-full">
    <!-- Banner -->
    <div
      v-if="!connected"
      class="mx-4 mt-2 px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700 flex items-center gap-2"
    >
      <span class="animate-spin text-xs">⏳</span>
      连接中断，正在重连...
    </div>

    <!-- Info -->
    <div class="px-4 pt-4 pb-2">
      <p class="text-xs text-gray-500">
        设备网关 Demo — 展示框架的 WebSocket 实时双向通信能力
      </p>
      <div class="mt-2 text-sm text-gray-700">
        已连接: <span class="font-semibold">{{ devices.filter(d => d.status === 'online').length }}</span>
        / {{ devices.length }} 台设备
      </div>
    </div>

    <!-- Device list -->
    <div class="flex-1 overflow-y-auto px-4 pb-2 space-y-2">
      <div v-if="devices.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm">
        <p class="text-2xl mb-2">📱</p>
        <p>暂无设备连接</p>
      </div>
      <DeviceCard
        v-for="d in devices"
        :key="d.device_id"
        :device="d"
        :expanded="selectedId === d.device_id"
        @select="selectedId = selectedId === d.device_id ? null : d.device_id"
      />
    </div>

    <!-- Send panel -->
    <div class="border-t border-gray-200 bg-white px-4 py-3 space-y-2">
      <select
        v-model="targetDevice"
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
      >
        <option value="">选择目标设备</option>
        <option
          v-for="d in devices.filter(d => d.status === 'online')"
          :key="d.device_id"
          :value="d.device_id"
        >
          {{ d.name }}
        </option>
      </select>
      <form class="flex gap-2" @submit.prevent="handleSend">
        <input
          v-model="commandInput"
          type="text"
          placeholder="输入命令..."
          class="flex-1 rounded-full border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          :disabled="!targetDevice"
        />
        <button
          type="submit"
          class="shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center disabled:opacity-40"
          :disabled="!targetDevice || !commandInput.trim()"
        >
          <span class="text-lg">↑</span>
        </button>
      </form>
    </div>

    <!-- Messages -->
    <div v-if="deviceMessages.length" class="border-t border-gray-100 px-4 py-2 max-h-32 overflow-y-auto">
      <div class="text-xs text-gray-500 mb-1">消息记录</div>
      <div
        v-for="(m, i) in deviceMessages.slice(-10)"
        :key="i"
        class="text-xs text-gray-600 py-0.5"
      >
        [{{ m.type }}] {{ JSON.stringify(m.payload).slice(0, 80) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import DeviceCard from '../components/devices/DeviceCard.vue'

const { devices, connected, deviceMessages, sendCommand } = useWebSocket()

const selectedId = ref<string | null>(null)
const targetDevice = ref('')
const commandInput = ref('')

function handleSend() {
  if (!targetDevice.value || !commandInput.value.trim()) return
  sendCommand(targetDevice.value, 'query', commandInput.value)
  commandInput.value = ''
}
</script>
```

- [ ] **Step 4: Verify TypeScript compilation**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vue-tsc --noEmit 2>&1 | tail -10"
```

- [ ] **Step 5: Commit**

```bash
git add web/src/composables/useWebSocket.ts web/src/components/devices/ web/src/views/DevicesView.vue
git commit -m "feat: 实现设备网关页面 - WebSocket 实时通信"
```

---

### Task 7: Plugins Page

**Files:**
- Modify: `web/src/views/PluginsView.vue`

- [ ] **Step 1: Implement PluginsView**

```vue
<!-- web/src/views/PluginsView.vue -->
<template>
  <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
    <div v-if="loading" class="flex items-center justify-center h-40 text-gray-400 text-sm">
      加载中...
    </div>
    <div v-else-if="error" class="flex flex-col items-center justify-center h-40 text-sm">
      <p class="text-red-500">{{ error }}</p>
      <button class="mt-2 text-blue-600 underline text-xs" @click="load">重试</button>
    </div>
    <template v-else>
      <div
        v-for="plugin in plugins"
        :key="plugin.name"
        class="rounded-lg border border-gray-200 bg-white p-4"
      >
        <div class="flex items-center gap-2 mb-2">
          <span class="font-medium text-sm text-gray-900">{{ plugin.name }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="typeColor(plugin.type)">
            {{ plugin.type }}
          </span>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="plugin.status === 'loaded' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'">
            {{ plugin.status }}
          </span>
          <span class="text-xs text-gray-400 ml-auto">v{{ plugin.version }}</span>
        </div>
        <div v-if="plugin.capabilities.length" class="flex flex-wrap gap-1">
          <span
            v-for="cap in plugin.capabilities"
            :key="cap"
            class="text-xs px-2 py-0.5 bg-gray-50 text-gray-600 rounded-full"
          >
            {{ cap }}
          </span>
        </div>
      </div>
      <div v-if="plugins.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm">
        <p class="text-2xl mb-2">🧩</p>
        <p>暂无插件</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchPlugins } from '../api/plugins'
import type { Plugin } from '../types'

const plugins = ref<Plugin[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function typeColor(type: string): string {
  const map: Record<string, string> = {
    agent: 'bg-blue-100 text-blue-700',
    memory: 'bg-purple-100 text-purple-700',
    search: 'bg-orange-100 text-orange-700',
    extension: 'bg-teal-100 text-teal-700',
  }
  return map[type] ?? 'bg-gray-100 text-gray-600'
}

async function load() {
  loading.value = true
  error.value = null
  try {
    plugins.value = await fetchPlugins()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 2: Verify full app compiles**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npx vue-tsc --noEmit 2>&1 | tail -10"
```

- [ ] **Step 3: Commit**

```bash
git add web/src/views/PluginsView.vue
git commit -m "feat: 实现插件列表页"
```

---

### Task 8: Build + nginx + Docker Integration

**Files:**
- Create: `nginx.conf` (project root)
- Modify: `docker-compose.yml`

- [ ] **Step 1: Build frontend**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE/web && npm run build"
```

Expected: `web/dist/` directory created with index.html and assets.

- [ ] **Step 2: Create nginx.conf**

```nginx
# nginx.conf (project root)
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://app:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # WebSocket proxy
    location /api/devices/ws {
        proxy_pass http://app:8000/api/devices/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }
}
```

- [ ] **Step 3: Add nginx service to docker-compose.yml**

Add to `docker-compose.yml` services section:

```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - app
    restart: unless-stopped
```

- [ ] **Step 4: Start nginx and verify end-to-end**

```bash
ssh root@218.244.148.190 "cd /root/workspace/Life-Agent-RU-YEE && docker compose up -d nginx"
ssh root@218.244.148.190 "curl -s http://localhost:80 | head -20"
ssh root@218.244.148.190 "curl -s http://localhost:80/api/health"
```

Expected: HTML from Vue app, and health check returns `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
# Add web/dist/ to .gitignore
echo "web/dist/" >> .gitignore
git add nginx.conf docker-compose.yml .gitignore
git commit -m "feat: 添加 nginx 反向代理和 Docker 集成"
```

---

### Task 9: End-to-End Verification

- [ ] **Step 1: Verify chat page works via browser**

```bash
# Test SSE stream via nginx
ssh root@218.244.148.190 'curl -s -N -X POST http://localhost:80/api/chat -H "Content-Type: application/json" -d "{\"message\": \"推荐一道低卡菜\"}" --max-time 30 2>&1 | head -20'
```

Expected: SSE events streaming back.

- [ ] **Step 2: Verify plugins page data**

```bash
ssh root@218.244.148.190 "curl -s http://localhost:80/api/plugins"
```

Expected: JSON with plugin list.

- [ ] **Step 3: Verify WebSocket endpoint is proxied**

```bash
ssh root@218.244.148.190 "curl -s -i -N -H 'Upgrade: websocket' -H 'Connection: Upgrade' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' -H 'Sec-WebSocket-Version: 13' http://localhost:80/api/devices/ws 2>&1 | head -10"
```

Expected: `101 Switching Protocols` response.

- [ ] **Step 4: Verify frontend is accessible externally**

Access `http://218.244.148.190` in browser. Verify:
- Chat page renders with empty state and input
- Bottom navigation works (3 tabs)
- Health status shows green/online
- Sending a message returns streaming response
- Plugins page shows loaded plugins
- Devices page shows WebSocket connection

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: 前端 Demo 完成 - 端到端验证通过"
```
