<script>
  import { onDestroy } from 'svelte'
  import { startAsr, getTaskStatus, getTaskResult, cancelTask } from './api.js'
  import { createTaskPoller } from './taskPoll.js'
  import { currentFileId, currentTaskId, taskStatus, progress, statusText, subtitleText, timestamps, subtitleEntries, language, hintText, stripPunct, capitalize } from './stores.js'
  import { translateError } from './errors.js'

  const poller = createTaskPoller(1000)
  let asrModel = $state('Qwen/Qwen3-ASR-0.6B')
  let selectAll = $state(true)
  let spaceReplacement = $state(false)
  let llmEnabled = $state(false)
  let showLlmWarning = $state(false)
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

  onDestroy(() => poller.stop())

  // Check LLM config and hint text to decide if warning needed
  async function checkLlmConfig() {
    try {
      const res = await fetch('/api/config')
      if (res.ok) {
        const cfg = await res.json()
        llmEnabled = cfg.llm_enabled
      }
    } catch { /* ignore */ }
  }
  checkLlmConfig()

  $effect(() => {
    showLlmWarning = !llmEnabled && $hintText.trim().length > 0
  })

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

  async function start() {
    const fid = $currentFileId
    if (!fid) return

    poller.stop()
    taskStatus.set('starting')
    progress.set(0)
    statusText.set('正在启动...')
    subtitleText.set('')
    timestamps.set([])
    subtitleEntries.set([])

    try {
      const result = await startAsr({
        file_id: fid,
        language: $language,
        hint_text: $hintText,
        split_point: 0,
        asr_model: asrModel,
        strip_punct: $stripPunct,
        capitalize: $capitalize,
        strip_mid_punct: getSelectedTypes().length > 0,
        mid_punct_choices: getSelectedTypes(),
        space_replacement: spaceReplacement,
      })
      currentTaskId.set(result.task_id)
      taskStatus.set('running')
      pollStatus(result.task_id)
    } catch (e) {
      taskStatus.set('failed')
      statusText.set(translateError(e.message || '启动失败'))
    }
  }

  function pollStatus(taskId) {
    poller.start(async () => {
      try {
        const st = await getTaskStatus(taskId)
        progress.set(st.progress)
        statusText.set(st.status_text || st.status)

        if (st.status === 'completed') {
          poller.stop()
          taskStatus.set('completed')
          const res = await getTaskResult(taskId)
          subtitleText.set(res.text)
          timestamps.set(res.timestamps)
          subtitleEntries.set(res.subtitle_entries || [])
        } else if (st.status === 'failed' || st.status === 'cancelled') {
          poller.stop()
          taskStatus.set(st.status)
          statusText.set(translateError(st.error || st.status_text || st.status))
        }
      } catch (e) {
        poller.stop()
        taskStatus.set('failed')
        statusText.set(translateError('轮询失败: ' + (e.message || '')))
      }
    })
  }

  async function cancel() {
    if ($currentTaskId) {
      await cancelTask($currentTaskId)
      poller.stop()
      taskStatus.set('cancelled')
      statusText.set('已取消')
    }
  }
</script>

<div class="panel">
  {#if showLlmWarning}
    <div class="warning-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <span>提示文字在未启用 LLM 校正时仅作为热词使用。请前往<strong>设置</strong> — 启用 LLM 校正并配置 LLM 以使用校正功能。</span>
    </div>
  {/if}

  <div class="form-grid">
    <div class="field">
      <span class="field-label">语言</span>
      <select bind:value={$language}>
        <option value="auto">自动检测</option>
        <option value="Chinese">中文</option>
        <option value="English">English</option>
        <option value="Japanese">日本語</option>
        <option value="Korean">한국어</option>
      </select>
    </div>
    <div class="field">
      <span class="field-label">模型</span>
      <select bind:value={asrModel}>
        <option value="Qwen/Qwen3-ASR-0.6B">Qwen3-ASR-0.6B</option>
        <option value="Qwen/Qwen3-ASR-1.7B">Qwen3-ASR-1.7B</option>
      </select>
    </div>
  </div>

  <div class="field">
    <span class="field-label">提示文字 <span class="hint">（可选，作为 ASR 热词）</span></span>
    <textarea
      bind:value={$hintText}
      placeholder="输入提示性文字，用于 ASR 热词或 LLM 校正..."
      rows="2"
    ></textarea>
  </div>

  <div class="opts-row">
    <label class="opt-check">
      <input type="checkbox" bind:checked={$stripPunct} />
      <span>删除句末标点</span>
    </label>
    <label class="opt-check">
      <input type="checkbox" bind:checked={$capitalize} />
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
    {#if $taskStatus === 'running' || $taskStatus === 'starting'}
      <button class="btn-danger" onclick={cancel}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        停止
      </button>
    {:else}
      <button class="btn-primary" onclick={start} disabled={!$currentFileId || $taskStatus === 'running'}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        开始识别
      </button>
    {/if}
  </div>

  {#if $taskStatus !== 'idle'}
    <div class="progress-section">
      <div class="bar-bg">
        <div class="bar-fill" style="width: {$progress * 100}%"></div>
      </div>
      <p class="st">{$statusText}</p>
    </div>
  {/if}
</div>

<style>
  .panel { margin: 0.25rem 0; display: flex; flex-direction: column; gap: 0.75rem; }
  .warning-banner {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.6rem 0.75rem;
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: 10px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.5;
  }
  .warning-banner svg {
    flex-shrink: 0;
    margin-top: 1px;
    color: #f59e0b;
  }
  .warning-banner strong {
    color: var(--accent);
    font-weight: 600;
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .field { display: flex; flex-direction: column; gap: 0.3rem; }
  .field-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
  }
  .hint {
    font-weight: 400;
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  select, textarea {
    width: 100%;
    padding: 0.5rem 0.7rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 0.88rem;
    transition: all 0.25s ease;
    font-family: inherit;
  }
  select:focus, textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
  }
  textarea { resize: vertical; }
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
  .st { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
</style>
