<script>
  import { uploadAudio } from './api.js'
  import { currentFileId, audioDuration, audioFileName, audioUrl, mode, taskStatus, progress, statusText, currentTaskId, subtitleText, timestamps, subtitleEntries } from './stores.js'

  let dragging = $state(false)
  let uploading = $state(false)
  let error = $state('')
  let fileInput = $state(null)

  function triggerFilePicker() {
    fileInput?.click()
  }

  async function handleFile(file) {
    error = ''
    uploading = true
    try {
      const result = await uploadAudio(file)
      currentFileId.set(result.file_id)
      audioDuration.set(result.duration)
      audioFileName.set(result.filename)
      audioUrl.set(`/uploads/${result.file_id}/converted.wav`)
      mode.set(null)
      taskStatus.set('idle')
      progress.set(0)
      statusText.set('')
      currentTaskId.set(null)
      subtitleText.set('')
      timestamps.set([])
      subtitleEntries.set([])
    } catch (e) {
      error = e.message || 'Upload failed'
    } finally {
      uploading = false
    }
  }

  function onDrop(e) {
    e.preventDefault()
    dragging = false
    const file = e.dataTransfer?.files?.[0]
    if (file) handleFile(file)
  }

  function onSelect(e) {
    const file = e.target?.files?.[0]
    if (file) handleFile(file)
  }
</script>

<div
  class="upload-zone"
  class:dragging
  class:uploading
  ondragover={(e) => { e.preventDefault(); dragging = true; }}
  ondragleave={() => dragging = false}
  ondrop={onDrop}
  onclick={triggerFilePicker}
  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') triggerFilePicker(); }}
  role="button"
  tabindex="0"
>
  {#if uploading}
    <p>上传中...</p>
  {:else if $audioFileName}
    <p class="file-info">{$audioFileName}</p>
    <p class="dur-info">时长: {$audioDuration.toFixed(1)} 秒</p>
    <label class="change-label">
      <input type="file" accept="audio/*" onchange={onSelect} hidden />
      更换文件
    </label>
  {:else}
    <p>拖拽音频文件到此处，或点击选择文件</p>
    <p class="hint">支持 mp3/wav/m4a/flac/aac/ogg/wma/opus</p>
    <input type="file" accept="audio/*" onchange={onSelect} hidden bind:this={fileInput} />
  {/if}
</div>

{#if error}
  <p class="error">{error}</p>
{/if}

<style>
  .upload-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 2.5rem 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s;
    background: var(--accent-dim);
  }
  .upload-zone:hover, .upload-zone.dragging {
    border-color: var(--accent);
    background: rgba(79, 195, 247, 0.08);
    box-shadow: 0 0 30px rgba(79, 195, 247, 0.06);
  }
  .upload-zone.uploading { opacity: 0.5; pointer-events: none; }
  .upload-zone p { margin: 0; color: var(--text-secondary); font-size: 0.9rem; }
  .file-info { font-size: 1.05rem; font-weight: 600; color: var(--accent) !important; }
  .dur-info { font-size: 0.8rem; color: var(--text-muted) !important; margin-top: 0.3rem !important; }
  .hint { font-size: 0.78rem; color: var(--text-muted) !important; margin-top: 0.6rem !important; }
  .change-label {
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--accent);
    margin-top: 0.5rem;
    display: inline-block;
    transition: opacity 0.2s;
  }
  .change-label:hover { opacity: 0.8; }
  .error { color: var(--red); margin-top: 0.5rem; font-size: 0.85rem; }
</style>
