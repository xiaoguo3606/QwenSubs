<script>
  import { playbackTime } from './stores.js'

  let { text = '', timestamps = [], onseek } = $props()
  let editing = $state('')
  let textarea = $state(null)
  let lastUserInteraction = $state(0)

  $effect(() => {
    editing = text || ''
  })

  export function getText() {
    return editing
  }

  export function setText(t) {
    editing = t
  }

  function handleCursorChange() {
    if (!textarea || !timestamps.length) return
    lastUserInteraction = Date.now()
    const pos = textarea.selectionStart
    let charIdx = 0
    for (let i = 0; i < pos && i < editing.length; i++) {
      if (editing[i] !== '\n') charIdx++
    }
    const idx = Math.min(charIdx, timestamps.length - 1)
    const ts = timestamps[idx]
    if (ts && onseek) onseek(ts.start_time)
  }

  $effect(() => {
    const unsub = playbackTime.subscribe(t => {
      if (!textarea || !timestamps.length || t == null || t <= 0) return

      // If user interacted recently, skip auto-scroll to avoid interference
      if (Date.now() - lastUserInteraction < 1500) return

      // Find character index in timestamps matching current playback time
      let charIdx = -1
      for (let i = 0; i < timestamps.length; i++) {
        if (t >= timestamps[i].start_time && t <= timestamps[i].end_time) {
          charIdx = i
          break
        }
      }
      if (charIdx === -1) return

      // Find which line this char belongs to in editing text
      let cc = 0
      const lines = editing.split('\n')
      let foundLine = -1
      for (let li = 0; li < lines.length; li++) {
        const nextCc = cc + lines[li].length
        if (charIdx >= cc && charIdx < nextCc) {
          foundLine = li
          break
        }
        cc = nextCc
      }
      if (foundLine === -1) return

      // Auto-scroll to bring current line to the top
      const style = getComputedStyle(textarea)
      const lh = parseFloat(style.lineHeight) || 24
      textarea.scrollTop = foundLine * lh
    })
    return unsub
  })
</script>

<div class="editor">
  <label class="label" for="subtitle-textarea">字幕文本（每行一条字幕）</label>
  <div class="textarea-wrap">
    <textarea
      bind:this={textarea}
      bind:value={editing}
      id="subtitle-textarea"
      class="textarea"
      placeholder="识别完成后，结果将显示在此处..."
      rows="12"
      onclick={handleCursorChange}
      onkeyup={handleCursorChange}
    ></textarea>
  </div>
</div>

<style>
  .editor { margin: 0.5rem 0; }
  .label { font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 0.4rem; font-weight: 500; }
  .textarea-wrap { position: relative; }
  .textarea {
    width: 100%;
    padding: 0.65rem 0.75rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.9rem;
    line-height: 1.7;
    resize: vertical;
    font-family: inherit;
    transition: border-color 0.25s;
  }
  .textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.1); }
</style>
