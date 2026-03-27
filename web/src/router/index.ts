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
