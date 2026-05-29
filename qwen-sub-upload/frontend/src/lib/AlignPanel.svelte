<script>
  import { onDestroy } from 'svelte'
  import { startAlign, getTaskStatus, getTaskResult, cancelTask } from './api.js'
  import { createTaskPoller } from './taskPoll.js'
  import { currentFileId, subtitleText, timestamps, subtitleEntries, language } from './stores.js'
  import { translateError } from './errors.js'

  const poller = createTaskPoller(1000)
  let alignText = $state('')
  let alignStatus = $state('idle')
  let alignProgress = $state(0)
  let alignStatusText = $state('')
  let alignTaskId = $state(null)

  onDestroy(() => poller.stop())

  function alignLanguage() {
    return $language === 'auto' ? 'Chinese' : $language
  }

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

    poller.stop()
    try {
      const result = await startAlign({
        file_id: fid,
        text: alignText,
        language: alignLanguage(),
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
      alignStatusText = translateError(e.message || '启动失败')
    }
  }

  function pollStatus(taskId) {
    poller.start(async () => {
      try {
        const st = await getTaskStatus(taskId)
        alignProgress = st.progress
        alignStatusText = translateError(st.error || st.status_text || st.status)

        if (st.status === 'completed') {
          poller.stop()
          alignStatus = 'completed'
          const res = await getTaskResult(taskId)
          subtitleText.set(res.text)
          timestamps.set(res.timestamps)
          subtitleEntries.set(res.subtitle_entries || [])
        } else if (st.status === 'failed' || st.status === 'cancelled') {
          poller.stop()
          alignStatus = st.status
          alignStatusText = translateError(st.error || st.status_text || st.status)
        }
      } catch (e) {
        poller.stop()
        alignStatus = 'failed'
        alignStatusText = translateError('轮询失败: ' + (e.message || ''))
      }
    })
  }

  async function cancel() {
    if (alignTaskId) {
      await cancelTask(alignTaskId)
      poller.stop()
      alignStatus = 'cancelled'
      alignStatusText = '已取消'
    }
  }
</script>

<div class="panel">
  <p class="hint">将已有字幕文本与音频进行强制对齐，修正时间轴精度</p>

  <div class="field">
    <span class="field-label">字幕文本</span>
    <textarea
      bind:value={alignText}
      placeholder="粘贴或输入与音频对应的完整文本..."
      rows="5"
    ></textarea>
  </div>

  <div class="opts-row">
    <label class="opt-check">
      <input type="checkbox" bind:checked={alignStripPunct} />
      <span>删除句末标点</span>
    </label>
    <label class="opt-check">
      <input type="checkbox" bind:checked={alignCapitalize} />
      <span>首字母大写</span>
    </label>
  </div>

  <details class="punct-options" open>
    <summary class="punct-summary">
      <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 18 15 12 9 6"/>
      </svg>
      删除句中标点符号
    </summary>
    <div class="punct-grid">
      {#each midTypes as t}
        <label class="punct-chip">
          <input type="checkbox" bind:checked={t.checked} />
          <span class="chip-label">{t.name}</span>
        </label>
      {/each}
      <label class="punct-chip punct-chip-all">
        <input type="checkbox" checked={selectAll} onchange={toggleAll} />
        <span class="chip-label">以上全部</span>
      </label>
      <label class="punct-chip punct-chip-space">
        <input type="checkbox" bind:checked={spaceReplacement} />
        <span class="chip-label">用一个空格代替</span>
      </label>
    </div>
  </details>

  <div class="actions">
    {#if alignStatus === 'running' || alignStatus === 'starting'}
      <button class="btn-danger" onclick={cancel}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        停止
      </button>
    {:else}
      <button class="btn-primary" onclick={start} disabled={!$currentFileId || !alignText.trim()}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        开始对齐
      </button>
    {/if}
  </div>

  {#if alignStatus !== 'idle'}
    <div class="progress-section">
      <div class="bar-bg">
        <div class="bar-fill" style="width: {alignProgress * 100}%"></div>
      </div>
      <p class="bar-text">{alignStatusText}</p>
    </div>
  {/if}
</div>

<style>
  .panel { margin: 0.25rem 0; display: flex; flex-direction: column; gap: 0.75rem; }
  .hint { font-size: 0.82rem; color: var(--text-muted); margin: 0; }
  .field { display: flex; flex-direction: column; gap: 0.3rem; }
  .field-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
  }
  textarea {
    width: 100%;
    padding: 0.55rem 0.75rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 0.88rem;
    resize: vertical;
    font-family: inherit;
    transition: all 0.25s ease;
  }
  textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08); }
  .opts-row {
    display: flex;
    gap: 1.25rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .opt-check {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
  }
  .opt-check input[type="checkbox"] {
    accent-color: var(--accent);
    width: 14px;
    height: 14px;
    margin: 0;
  }
  .punct-options {
    background: rgba(255,255,255,0.015);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.6rem 0.85rem;
  }
  .punct-summary {
    font-size: 0.85rem;
    color: var(--text-secondary);
    cursor: pointer;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    user-select: none;
    list-style: none;
  }
  .punct-summary::-webkit-details-marker { display: none; }
  .punct-summary::marker { display: none; content: ''; }
  .chevron {
    transition: transform 0.25s ease;
  }
  details[open] .chevron {
    transform: rotate(90deg);
  }
  .punct-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
  .punct-chip {
    display: flex;
    align-items: center;
    cursor: pointer;
  }
  .punct-chip input[type="checkbox"] {
    display: none;
  }
  .chip-label {
    font-size: 0.78rem;
    color: var(--text-muted);
    padding: 0.25rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    transition: all 0.2s ease;
    background: transparent;
  }
  .punct-chip input:checked + .chip-label {
    color: var(--accent);
    border-color: rgba(59, 130, 246, 0.25);
    background: var(--accent-dim);
  }
  .punct-chip-all .chip-label { font-weight: 600; }
  .punct-chip-all input:checked + .chip-label { color: var(--accent-secondary); border-color: rgba(6, 182, 212, 0.25); background: var(--accent-secondary-dim); }
  .punct-chip-space .chip-label { font-weight: 500; }
  .punct-chip-space input:checked + .chip-label { color: var(--green); border-color: rgba(34, 197, 94, 0.25); background: var(--green-dim); }
  .actions { margin-top: 0.25rem; }
  .progress-section { margin-top: 0.25rem; }
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
  .bar-text { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
</style>
