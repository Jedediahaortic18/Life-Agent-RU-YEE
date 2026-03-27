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
