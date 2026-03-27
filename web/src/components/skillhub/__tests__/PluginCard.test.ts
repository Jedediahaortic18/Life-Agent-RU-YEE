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
