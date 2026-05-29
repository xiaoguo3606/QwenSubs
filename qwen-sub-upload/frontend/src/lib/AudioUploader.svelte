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
    <div class="upload-icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
    </div>
    <p class="upload-status">上传中...</p>
    <div class="upload-progress">
      <div class="upload-progress-bar"></div>
    </div>
  {:else if $audioFileName}
    <div class="file-info-icon">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
    </div>
    <p class="file-name">{$audioFileName}</p>
    <p class="file-dur">时长 {$audioDuration.toFixed(1)} 秒</p>
    <label class="change-btn">
      <input type="file" accept="audio/*" onchange={onSelect} hidden />
      更换文件
    </label>
  {:else}
    <div class="upload-icon">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
    </div>
    <p class="upload-text">拖拽音频文件到此处，或点击选择</p>
    <p class="upload-hint">支持 mp3 / wav / m4a / flac / aac / ogg / wma / opus</p>
    <input type="file" accept="audio/*" onchange={onSelect} hidden bind:this={fileInput} />
  {/if}
</div>

{#if error}
  <p class="error-msg">{error}</p>
{/if}

<style>
  .upload-zone {
    border: 1.5px dashed var(--border);
    border-radius: 14px;
    padding: 2.5rem 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.35s ease;
    background: transparent;
  }
  .upload-zone:hover, .upload-zone.dragging {
    border-color: var(--accent);
    background: rgba(59, 130, 246, 0.04);
    box-shadow: 0 0 40px rgba(59, 130, 246, 0.05);
  }
  .upload-zone.uploading {
    opacity: 0.6;
    pointer-events: none;
    border-color: var(--accent-secondary);
    border-style: solid;
  }
  .upload-icon {
    color: var(--text-muted);
    display: flex;
    justify-content: center;
    margin-bottom: 0.75rem;
    transition: color 0.3s;
  }
  .upload-zone:hover .upload-icon {
    color: var(--accent);
  }
  .upload-text {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 500;
  }
  .upload-hint {
    margin: 0.5rem 0 0;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .upload-status {
    margin: 0;
    color: var(--accent-secondary);
    font-size: 0.9rem;
  }
  .upload-progress {
    max-width: 200px;
    margin: 0.75rem auto 0;
    height: 3px;
    background: rgba(255,255,255,0.04);
    border-radius: 4px;
    overflow: hidden;
  }
  .upload-progress-bar {
    height: 100%;
    width: 40%;
    background: var(--gradient-2);
    border-radius: 4px;
    animation: shimmer 1.2s ease-in-out infinite;
    background-size: 200% 100%;
  }
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
  }
  .file-info-icon {
    color: var(--accent);
    display: flex;
    justify-content: center;
    margin-bottom: 0.5rem;
  }
  .file-name {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
  }
  .file-dur {
    margin: 0.25rem 0 0;
    font-size: 0.8rem;
    color: var(--text-muted);
  }
  .change-btn {
    display: inline-block;
    margin-top: 0.75rem;
    font-size: 0.8rem;
    color: var(--accent);
    cursor: pointer;
    padding: 0.3rem 0.8rem;
    border: 1px solid rgba(245, 158, 11, 0.15);
    border-radius: 8px;
    background: var(--accent-dim);
    transition: all 0.2s;
    font-weight: 500;
  }
  .change-btn:hover {
    background: rgba(59, 130, 246, 0.18);
    border-color: rgba(59, 130, 246, 0.3);
  }
  .error-msg {
    color: var(--red);
    margin-top: 0.5rem;
    font-size: 0.85rem;
  }
</style>
