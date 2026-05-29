import { writable } from 'svelte/store'

export const currentFileId = writable(null)
export const audioDuration = writable(0)
export const audioFileName = writable('')
export const audioUrl = writable(null)

export const currentTaskId = writable(null)
export const taskStatus = writable('idle')
export const progress = writable(0)
export const statusText = writable('')

export const subtitleText = writable('')
export const timestamps = writable([])
export const subtitleEntries = writable([])

export const splitPoint = writable(0)
export const language = writable('auto')
export const hintText = writable('')
export const stripPunct = writable(true)
export const capitalize = writable(false)

export const mode = writable(null) // 'asr' | 'align' | null

export const playbackTime = writable(0)
