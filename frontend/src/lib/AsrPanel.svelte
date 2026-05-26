<script>
  import { startAsr, getTaskStatus, getTaskResult, cancelTask } from './api.js'
  import { currentFileId, currentTaskId, taskStatus, progress, statusText, subtitleText, timestamps, subtitleEntries, language, hintText, stripPunct, capitalize } from './stores.js'

  let polling = $state(null)
  let asrModel = $state('Qwen/Qwen3-ASR-0.6B')
  let selectAll = $state(true)
  let spaceReplacement = $state(false)
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

  async function start() {
    const fid = $currentFileId
    if (!fid) return

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
      statusText.set('启动失败: ' + (e.message || ''))
    }
  }

  function pollStatus(taskId) {
    polling = setInterval(async () => {
      try {
        const st = await getTaskStatus(taskId)
        progress.set(st.progress)
        statusText.set(st.status_text || st.status)

        if (st.status === 'completed') {
          clearInterval(polling)
          polling = null
          taskStatus.set('completed')
          const res = await getTaskResult(taskId)
          subtitleText.set(res.text)
          timestamps.set(res.timestamps)
          subtitleEntries.set(res.subtitle_entries || [])
        } else if (st.status === 'failed' || st.status === 'cancelled') {
          clearInterval(polling)
          polling = null
          taskStatus.set(st.status)
          statusText.set(st.error || st.status)
        }
      } catch (e) {
        clearInterval(polling)
        polling = null
        taskStatus.set('failed')
        statusText.set('轮询失败: ' + (e.message || ''))
      }
    }, 1000)
  }

  async function cancel() {
    if ($currentTaskId) {
      await cancelTask($currentTaskId)
      if (polling) {
        clearInterval(polling)
        polling = null
      }
      taskStatus.set('cancelled')
      statusText.set('已取消')
    }
  }
</script>

<div class="panel">
  <div class="row">
    <select bind:value={$language}>
      <option value="auto">自动检测</option>
      <option value="Chinese">中文</option>
      <option value="English">English</option>
      <option value="Japanese">日本語</option>
      <option value="Korean">한국어</option>
    </select>
  </div>

  <div class="row">
    <select bind:value={asrModel}>
      <option value="Qwen/Qwen3-ASR-0.6B">Qwen3-ASR-0.6B</option>
      <option value="Qwen/Qwen3-ASR-1.7B">Qwen3-ASR-1.7B</option>
    </select>
  </div>

  <div class="row">
    <textarea
      bind:value={$hintText}
      placeholder="提示性文字（可选，用于校正专有名词）"
      rows="2"
    ></textarea>
  </div>

  <div class="row opts">
    <label><input type="checkbox" bind:checked={$stripPunct} /> 删除句末标点</label>
    <label><input type="checkbox" bind:checked={$capitalize} /> 首字母大写</label>
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
    {#if $taskStatus === 'running' || $taskStatus === 'starting'}
      <button class="btn-danger" onclick={cancel}>停止</button>
    {:else}
      <button class="btn-primary" onclick={start} disabled={!$currentFileId || $taskStatus === 'running'}>
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
  .panel { margin: 0.5rem 0; }
  .row { margin: 0.5rem 0; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .opts { gap: 1rem; }
  .opts label { font-size: 0.85rem; color: var(--text-secondary); cursor: pointer; display: flex; align-items: center; gap: 0.35rem; }
  .opts input[type="checkbox"] { accent-color: var(--accent); width: 14px; height: 14px; }
  select, textarea, input[type="number"] {
    width: 100%;
    padding: 0.45rem 0.65rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 0.88rem;
    transition: border-color 0.25s;
  }
  select:focus, textarea:focus, input[type="number"]:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.1);
  }
  textarea { resize: vertical; }
  .hint { font-size: 0.78rem; color: var(--text-muted); margin-left: 0.5rem; }
  .actions { margin-top: 0.75rem; }
  .progress-section { margin-top: 0.75rem; }
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
  .st { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
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
