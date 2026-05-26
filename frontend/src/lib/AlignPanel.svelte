<script>
  import { startAlign, getTaskStatus, getTaskResult, cancelTask } from './api.js'
  import { currentFileId, currentTaskId, taskStatus, progress, statusText, subtitleText, timestamps, subtitleEntries, language } from './stores.js'

  let alignText = $state('')
  let alignStatus = $state('idle')
  let alignProgress = $state(0)
  let alignStatusText = $state('')
  let alignTaskId = $state(null)
  let polling = $state(null)
  let selectAll = $state(true)
  let spaceReplacement = $state(false)
  let alignStripPunct = $state(true)
  let alignCapitalize = $state(false)
  let midTypes = $state([
    { name: '单引号', checked: true },
    { name: '双引号', checked: true },
    { name: '破折号', checked: true },
    { name: '连接号', checked: true },
    { name: '下划线', checked: true },
    { name: '方括号', checked: true },
    { name: '括号', checked: true },
    { name: '星号', checked: true },
    { name: '正反斜杠', checked: true },
    { name: '顿号', checked: true },
    { name: '书名号', checked: true },
    { name: '冒号', checked: true },
    { name: '间隔号', checked: true },
  ])

  $effect(() => {
    const all = midTypes.every(t => t.checked)
    if (all !== selectAll) selectAll = all
  })

  function toggleAll() {
    selectAll = !selectAll
    for (const t of midTypes) t.checked = selectAll
  }

  function getSelectedTypes() {
    if (selectAll) return ['以上全部']
    return midTypes.filter(t => t.checked).map(t => t.name)
  }

  $effect(() => {
    if ($subtitleText && !alignText) {
      alignText = $subtitleText
    }
  })

  async function start() {
    const fid = $currentFileId
    if (!fid || !alignText.trim()) return

    alignStatus = 'starting'
    alignProgress = 0
    alignStatusText = '正在启动对齐...'

    try {
      const result = await startAlign({
        file_id: fid,
        text: alignText,
        language: $language,
        split_point: 0,
        strip_punct: alignStripPunct,
        strip_mid_punct: getSelectedTypes().length > 0,
        mid_punct_choices: getSelectedTypes(),
        space_replacement: spaceReplacement,
        capitalize: alignCapitalize,
      })
      alignTaskId = result.task_id
      alignStatus = 'running'
      pollStatus(result.task_id)
    } catch (e) {
      alignStatus = 'failed'
      alignStatusText = '启动失败: ' + (e.message || '')
    }
  }

  function pollStatus(taskId) {
    polling = setInterval(async () => {
      try {
        const st = await getTaskStatus(taskId)
        alignProgress = st.progress
        alignStatusText = st.status_text || st.status

        if (st.status === 'completed') {
          clearInterval(polling)
          polling = null
          alignStatus = 'completed'
          const res = await getTaskResult(taskId)
          subtitleText.set(res.text)
          timestamps.set(res.timestamps)
          subtitleEntries.set(res.subtitle_entries || [])
        } else if (st.status === 'failed' || st.status === 'cancelled') {
          clearInterval(polling)
          polling = null
          alignStatus = st.status
          alignStatusText = st.status_text || st.status
        }
      } catch (e) {
        clearInterval(polling)
        polling = null
        alignStatus = 'failed'
        alignStatusText = '轮询失败: ' + (e.message || '')
      }
    }, 1000)
  }

  async function cancel() {
    if (alignTaskId) {
      await cancelTask(alignTaskId)
      if (polling) {
        clearInterval(polling)
        polling = null
      }
      alignStatus = 'cancelled'
      alignStatusText = '已取消'
    }
  }
</script>

<div class="panel">
  <p class="hint">将已有字幕文本与音频进行强制对齐，修正时间轴精度</p>

  <div class="row">
    <textarea
      bind:value={alignText}
      placeholder="粘贴或输入与音频对应的完整文本..."
      rows="5"
    ></textarea>
  </div>

  <div class="row opts">
    <label><input type="checkbox" bind:checked={alignStripPunct} /> 删除句末标点</label>
    <label><input type="checkbox" bind:checked={alignCapitalize} /> 首字母大写</label>
  </div>

  <details class="punct-options" open>
    <summary class="punct-summary">删除句中标点符号</summary>
    <div class="punct-grid">
      {#each midTypes as t}
        <label class="opt-item">
          <input type="checkbox" bind:checked={t.checked} /> {t.name}
        </label>
      {/each}
      <label class="opt-all">
        <input type="checkbox" checked={selectAll} onchange={toggleAll} /> 以上全部
      </label>
      <label class="opt-space">
        <input type="checkbox" bind:checked={spaceReplacement} /> 使用一个空格代替
      </label>
    </div>
  </details>

  <div class="row actions">
    {#if alignStatus === 'running' || alignStatus === 'starting'}
      <button class="btn-sm btn-danger" onclick={cancel}>停止</button>
    {:else}
      <button class="btn-sm btn-primary" onclick={start} disabled={!$currentFileId || !alignText.trim()}>
        开始对齐
      </button>
    {/if}
  </div>

  {#if alignStatus !== 'idle'}
    <div class="progress-bar">
      <div class="bar-bg">
        <div class="bar-fill" style="width: {alignProgress * 100}%"></div>
      </div>
      <p class="bar-text">{alignStatusText}</p>
    </div>
  {/if}
</div>

<style>
  .panel { margin: 0.5rem 0; }
  .hint { font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.6rem; }
  .row { margin: 0.5rem 0; }
  textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.88rem;
    resize: vertical;
    font-family: inherit;
    transition: border-color 0.25s;
  }
  textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.1); }
  .actions { margin-top: 0.75rem; display: flex; gap: 0.5rem; }
  .btn-sm {
    padding: 0.45rem 1.2rem;
    border-radius: 8px;
    font-size: 0.83rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.25s;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .btn-sm:active { transform: scale(0.97); }
  .btn-primary {
    background: var(--gradient-2);
    color: #fff;
    box-shadow: 0 4px 14px rgba(79, 195, 247, 0.25);
  }
  .btn-primary:hover:not(:disabled) {
    box-shadow: 0 6px 20px rgba(79, 195, 247, 0.35);
    transform: translateY(-1px);
  }
  .btn-primary:disabled { opacity: 0.35; cursor: not-allowed; transform: none !important; }
  .btn-danger {
    background: rgba(231,76,60,0.2);
    color: #e74c3c;
    border: 1px solid rgba(231,76,60,0.3);
  }
  .btn-danger:hover { background: rgba(231,76,60,0.3); }
  .progress-bar { margin-top: 0.75rem; }
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
  .bar-text { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
  .opts { gap: 1rem; display: flex; align-items: center; flex-wrap: wrap; margin: 0.5rem 0; }
  .opts label { font-size: 0.85rem; color: var(--text-secondary); cursor: pointer; display: flex; align-items: center; gap: 0.35rem; }
  .opts input[type="checkbox"] { accent-color: var(--accent); width: 14px; height: 14px; }
  .punct-options {
    margin: 0.5rem 0;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
  }
  .punct-summary {
    font-size: 0.85rem;
    color: var(--text-primary);
    cursor: pointer;
    font-weight: 500;
  }
  .punct-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 0.8rem;
    margin-top: 0.5rem;
  }
  .punct-grid label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  .punct-grid input[type="checkbox"] { accent-color: var(--accent); width: 13px; height: 13px; margin: 0; }
  .opt-all { font-weight: 600; color: var(--accent) !important; }
  .opt-space { font-weight: 500; color: var(--green) !important; }

</style>
