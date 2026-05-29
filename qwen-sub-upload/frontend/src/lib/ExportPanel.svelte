<script>
  import { onDestroy } from 'svelte'
  import { startAlign, getTaskStatus, getTaskResult, cancelTask, generateSubtitles } from './api.js'
  import { createTaskPoller } from './taskPoll.js'
  import { currentFileId, subtitleText, timestamps, subtitleEntries, language } from './stores.js'
  import { translateError } from './errors.js'

  const poller = createTaskPoller(1000)
  let format = $state('srt')
  let downloadUrl = $state('')
  let generating = $state(false)
  let aligning = $state(false)
  let alignStatus = $state('')
  let alignProgress = $state(0)
  let error = $state('')
  let editorEl
  let alignTaskId = $state(null)

  onDestroy(() => poller.stop())

  export function setEditor(el) {
    editorEl = el
  }

  function alignLanguage() {
    return $language === 'auto' ? 'Chinese' : $language
  }

  function cleanup() {
    poller.stop()
    aligning = false
    generating = false
  }

  async function generate() {
    const text = editorEl?.getText?.() || $subtitleText
    if (!text || text.trim() === '') return

    error = ''
    downloadUrl = ''

    const fid = $currentFileId
    if (!fid) {
      error = '请先上传音频文件'
      return
    }

    aligning = true
    alignStatus = '正在启动对齐...'
    alignProgress = 0

    try {
      const result = await startAlign({
        file_id: fid,
        text,
        language: alignLanguage(),
        split_point: 0,
        strip_punct: false,
        strip_mid_punct: false,
        mid_punct_choices: [],
        space_replacement: false,
        capitalize: false,
      })
      alignTaskId = result.task_id
      alignStatus = '正在对齐...'

      await new Promise((resolve, reject) => {
        poller.start(async () => {
          try {
            const st = await getTaskStatus(result.task_id)
            alignProgress = st.progress
            alignStatus = st.error || st.status_text || st.status

            if (st.status === 'completed') {
              poller.stop()
              resolve()
            } else if (st.status === 'failed' || st.status === 'cancelled') {
              poller.stop()
              reject(new Error(translateError(st.error || st.status_text || st.status)))
            }
          } catch (e) {
            poller.stop()
            reject(e)
          }
        })
      })

      const aligned = await getTaskResult(result.task_id)
      subtitleText.set(aligned.text)
      timestamps.set(aligned.timestamps)
      subtitleEntries.set(aligned.subtitle_entries || [])

      aligning = false
      generating = true

      const genResult = await generateSubtitles({
        text: aligned.text,
        timestamps: aligned.timestamps,
        format,
      })
      downloadUrl = genResult.file_url
    } catch (e) {
      cleanup()
      error = translateError(e.message || '生成失败')
    } finally {
      generating = false
    }
  }

  async function cancel() {
    if (alignTaskId) {
      await cancelTask(alignTaskId)
    }
    cleanup()
    alignStatus = '已取消'
    error = '已取消'
  }
</script>

<div class="export">
  <div class="format-group">
    <span class="format-label">输出格式</span>
    <div class="format-options">
      {#each ['srt', 'ass', 'vtt'] as f}
        <label class="format-chip" class:active={format === f}>
          <input type="radio" bind:group={format} value={f} />
          <span class="chip-text">{f.toUpperCase()}</span>
        </label>
      {/each}
    </div>
  </div>

  <div class="actions">
    {#if aligning}
      <button class="btn-danger" onclick={cancel}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        停止
      </button>
      <span class="align-status">{alignStatus}</span>
    {:else if generating}
      <button disabled class="btn-generate">生成中...</button>
    {:else}
      <button class="btn-generate" onclick={generate} disabled={!$currentFileId}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        生成字幕
      </button>
    {/if}

    {#if downloadUrl}
      <a href={downloadUrl} class="download-link" download>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        下载 {format.toUpperCase()} 文件
      </a>
    {/if}
  </div>

  {#if aligning}
    <div class="progress-section">
      <div class="bar-bg">
        <div class="bar-fill" style="width: {alignProgress * 100}%"></div>
      </div>
    </div>
  {/if}

  {#if error}
    <p class="error-msg">{error}</p>
  {/if}
</div>

<style>
  .export { margin: 0.25rem 0; display: flex; flex-direction: column; gap: 0.75rem; }
  .format-group { display: flex; align-items: center; gap: 0.75rem; }
  .format-label { font-size: 0.8rem; color: var(--text-secondary); font-weight: 500; }
  .format-options { display: flex; gap: 0.4rem; }
  .format-chip {
    cursor: pointer;
  }
  .format-chip input[type="radio"] { display: none; }
  .chip-text {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 8px;
    transition: all 0.2s ease;
    background: transparent;
  }
  .format-chip.active .chip-text,
  .format-chip input:checked + .chip-text {
    color: var(--accent);
    border-color: rgba(59, 130, 246, 0.25);
    background: var(--accent-dim);
  }
  .actions { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
  .btn-generate {
    padding: 0.5rem 1.4rem;
    background: var(--gradient-3);
    color: #0c0c0e;
    border: none;
    border-radius: 10px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 700;
    box-shadow: 0 4px 16px rgba(34, 197, 94, 0.25);
    transition: all 0.25s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .btn-generate:hover:not(:disabled) {
    box-shadow: 0 6px 24px rgba(34, 197, 94, 0.35);
    transform: translateY(-1px);
  }
  .btn-generate:disabled { opacity: 0.3; cursor: not-allowed; transform: none !important; }
  .btn-danger {
    padding: 0.5rem 1.4rem;
    background: var(--red-dim);
    color: var(--red);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
  }
  .btn-danger:hover { background: rgba(239, 68, 68, 0.2); }
  .align-status { font-size: 0.82rem; color: var(--text-muted); }
  .download-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.5rem 1rem;
    background: var(--accent-dim);
    border-radius: 10px;
    color: var(--accent);
    font-size: 0.85rem;
    font-weight: 600;
    text-decoration: none;
    transition: all 0.25s ease;
    border: 1px solid rgba(59, 130, 246, 0.15);
  }
  .download-link:hover {
    background: rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.3);
    text-decoration: none;
    color: var(--accent);
  }
  .error-msg { color: var(--red); margin: 0; font-size: 0.85rem; }
  .progress-section { }
  .bar-bg {
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.04);
    border-radius: 4px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: var(--gradient-2);
    transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
    border-radius: 4px;
  }
</style>
