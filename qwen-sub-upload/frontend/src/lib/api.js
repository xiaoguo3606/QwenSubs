const API = '/api'

export async function uploadAudio(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function startAsr(params) {
  const res = await fetch(`${API}/asr/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function startAlign(params) {
  const res = await fetch(`${API}/align/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getTaskStatus(taskId) {
  const res = await fetch(`${API}/tasks/${taskId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getTaskResult(taskId) {
  const res = await fetch(`${API}/tasks/${taskId}/result`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function cancelTask(taskId) {
  const res = await fetch(`${API}/tasks/${taskId}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function generateSubtitles(params) {
  const res = await fetch(`${API}/subtitles/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
