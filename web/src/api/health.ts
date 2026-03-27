export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    return data.status === 'ok'
  } catch {
    return false
  }
}
