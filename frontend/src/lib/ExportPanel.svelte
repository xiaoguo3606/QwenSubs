<script>
  import { startAlign, getTaskStatus, getTaskResult, cancelTask, generateSubtitles } from './api.js'
  import { currentFileId, subtitleText, timestamps, subtitleEntries, language } from './stores.js'

  let format = $state('srt')
  let downloadUrl = $state('')
  let generating = $state(false)
  let aligning = $state(false)
  let alignStatus = $state('')
  let alignProgress = $state(0)
  let error = $state('')
  let editorEl
  let polling = $state(null)
  let alignTaskId = $state(null)

  export function setEditor(el) {
    editorEl = el
  }

  function cleanup() {
    if (polling) {
      clearInterval(polling)
      polling = null
    }
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
      error = '请先上传音频'
      return
    }

    // Step 1: Run forced alignment
    aligning = true
    alignStatus = '正在启动对齐...'
    alignProgress = 0

    try {
      const result = await startAlign({
        file_id: fid,
        text,
        language: $language,
        split_point: 0,
        strip_punct: false,
        strip_mid_punct: false,
        mid_punct_choices: [],
        space_replacement: false,
        capitalize: false,
      })
      alignTaskId = result.task_id
      alignStatus = '正在对齐...'

      // Step 2: Poll for alignment completion
      await new Promise((resolve, reject) => {
        polling = setInterval(async () => {
          try {
            const st = await getTaskStatus(result.task_id)
            alignProgress = st.progress
            alignStatus = st.status_text || st.status

            if (st.status === 'completed') {
              clearInterval(polling)
              polling = null
              resolve()
            } else if (st.status === 'failed' || st.status === 'cancelled') {
              clearInterval(polling)
              polling = null
              reject(new Error(st.error || st.status))
            }
          } catch (e) {
            clearInterval(polling)
            polling = null
            reject(e)
          }
        }, 1000)
      })

      // Step 3: Get alignment result
      const aligned = await getTaskResult(result.task_id)
      subtitleText.set(aligned.text)
      timestamps.set(aligned.timestamps)
      subtitleEntries.set(aligned.subtitle_entries || [])

      // Step 4: Generate subtitle file
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
      error = e.message || '生成失败'
    } finally {
      generating = false
    }
  }

  function cancel() {
    if (alignTaskId) {
      cancelTask(alignTaskId)
    }
    cleanup()
    alignStatus = '已取消'
    error = '已取消'
  }
</script>

<div class="export">
  <div class="row">
    <fieldset class="format-group">
      <legend class="format-label">输出格式:</legend>
      {#each ['srt', 'ass', 'vtt'] as f}
        <label class="radio">
          <input type="radio" bind:group={format} value={f} />
          <span class="radio-label">{f.toUpperCase()}</span>
        </label>
      {/each}
    </fieldset>
  </div>

  <div class="actions">
    {#if aligning}
      <button class="btn-danger" onclick={cancel}>停止</button>
      <span class="align-status">{alignStatus}</span>
    {:else if generating}
      <button class="generate" disabled>生成中...</button>
    {:else}
      <button class="generate" onclick={generate} disabled={!$currentFileId}>
        生成字幕
      </button>
    {/if}

    {#if downloadUrl}
      <a href={downloadUrl} class="download-link" download>下载字幕文件</a>
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
    <p class="error">{error}</p>
  {/if}
</div>

<style>
  .export { margin: 0.5rem 0; }
  .row { margin: 0.5rem 0; display: flex; align-items: center; gap: 0.5rem; }
  .format-group { border: none; padding: 0; margin: 0; display: flex; align-items: center; gap: 0.75rem; }
  .format-label { font-size: 0.85rem; color: var(--text-secondary); font-weight: 500; margin-right: 0.25rem; }
  .radio {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-secondary);
    transition: color 0.2s;
  }
  .radio input[type="radio"] { accent-color: var(--accent); width: 14px; height: 14px; margin: 0; }
  .radio:has(input:checked) { color: var(--accent); }
  .radio-label { font-weight: 500; }
  .actions { display: flex; align-items: center; gap: 0.75rem; margin-top: 0.75rem; flex-wrap: wrap; }
  .generate {
    padding: 0.5rem 1.4rem;
    background: var(--gradient-3);
    color: #0a0a1a;
    border: none;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(46, 204, 113, 0.25);
    transition: all 0.25s;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .generate:hover:not(:disabled) { box-shadow: 0 6px 20px rgba(46, 204, 113, 0.35); transform: translateY(-1px); }
  .generate:disabled { opacity: 0.35; cursor: not-allowed; transform: none !important; }
  .generate:active { transform: scale(0.97); }
  .btn-danger {
    padding: 0.5rem 1.4rem;
    background: rgba(231,76,60,0.2);
    color: #e74c3c;
    border: 1px solid rgba(231,76,60,0.3);
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.25s;
  }
  .btn-danger:hover { background: rgba(231,76,60,0.3); }
  .align-status { font-size: 0.82rem; color: var(--text-muted); }
  .download-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.5rem 1rem;
    background: var(--accent-dim);
    border-radius: 8px;
    color: var(--accent);
    font-size: 0.85rem;
    font-weight: 500;
    text-decoration: none;
    transition: all 0.25s;
  }
  .download-link:hover { background: rgba(79, 195, 247, 0.25); text-decoration: none; color: var(--accent); }
  .error { color: var(--red); margin-top: 0.5rem; font-size: 0.85rem; }
  .progress-section { margin-top: 0.5rem; }
  .bar-bg {
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: var(--gradient-2);
    transition: width 0.4s ease;
    border-radius: 2px;
  }
</style>
