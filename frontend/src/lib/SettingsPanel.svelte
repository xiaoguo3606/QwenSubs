<script>
  import { onDestroy, onMount } from 'svelte'
  import { createTaskPoller } from './taskPoll.js'

  const downloadPoller = createTaskPoller(2000)
  let config = $state(null)
  let models = $state([])
  let hardwareInfo = $state(null)
  let loading = $state(true)
  let saving = $state(false)
  let saved = $state(false)
  let error = $state('')
  let llmTesting = $state(false)
  let llmTestResult = $state(null)
  let llmTestError = $state('')

  onDestroy(() => downloadPoller.stop())

  async function loadAll() {
    try {
      const [cRes, mRes, hRes] = await Promise.all([
        fetch('/api/config'),
        fetch('/api/models'),
        fetch('/api/hardware'),
      ])
      if (!cRes.ok) throw new Error(await cRes.text())
      if (!mRes.ok) throw new Error(await mRes.text())
      if (!hRes.ok) throw new Error(await hRes.text())
      config = await cRes.json()
      models = (await mRes.json()).models
      hardwareInfo = await hRes.json()
    } catch (e) {
      error = '加载失败: ' + (e.message || '')
    } finally {
      loading = false
    }
  }

  async function testLlmConnection() {
    llmTesting = true
    llmTestResult = null
    llmTestError = ''
    try {
      const res = await fetch('/api/config/test-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          llm_type: config.llm_type,
          ollama_endpoint: config.ollama_endpoint,
          ollama_model: config.ollama_model,
          openai_base_url: config.openai_base_url,
          openai_api_key: config.openai_api_key,
          openai_model: config.openai_model,
        }),
      })
      const data = await res.json()
      if (data.status === 'ok') {
        llmTestResult = true
      } else {
        llmTestResult = false
        llmTestError = data.message || '连接失败'
      }
    } catch (e) {
      llmTestResult = false
      llmTestError = e.message || '连接失败'
    } finally {
      llmTesting = false
    }
  }

  async function save() {
    saving = true
    saved = false
    error = ''
    try {
      const res = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device: config.device,
          dtype: config.dtype,
          asr_model: config.asr_model,
          aligner_model: config.aligner_model,
          llm_enabled: config.llm_enabled,
          llm_type: config.llm_type,
          ollama_endpoint: config.ollama_endpoint,
          ollama_model: config.ollama_model,
          openai_base_url: config.openai_base_url,
          openai_api_key: config.openai_api_key,
          openai_model: config.openai_model,
          lang: config.lang,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      saved = true
      setTimeout(() => saved = false, 2000)
    } catch (e) {
      error = '保存失败: ' + (e.message || '')
    } finally {
      saving = false
    }
  }

  async function downloadModel(modelId) {
    try {
      const res = await fetch('/api/models/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId, source: 'modelscope' }),
      })
      if (!res.ok) throw new Error(await res.text())
      const { task_id } = await res.json()
      downloadPoller.stop()
      downloadPoller.start(async () => {
        try {
          const stRes = await fetch(`/api/tasks/${task_id}`)
          if (!stRes.ok) throw new Error(await stRes.text())
          const st = await stRes.json()
          if (st.status === 'completed') {
            downloadPoller.stop()
            loadAll()
          } else if (st.status === 'failed' || st.status === 'cancelled') {
            downloadPoller.stop()
            error = '下载失败: ' + (st.error || st.status_text || st.status)
          }
        } catch (e) {
          downloadPoller.stop()
          error = '下载状态查询失败: ' + (e.message || '')
        }
      })
    } catch (e) {
      error = '启动下载失败: ' + (e.message || '')
    }
  }

  onMount(loadAll)

  // Determine available device options based on detected hardware
  function getDeviceOptions() {
    const opts = [
      { value: 'auto', label: null, disabled: false },
    ]
    if (hardwareInfo) {
      opts[0].label = `自动 (${hardwareInfo.device.toUpperCase()})`
      opts.push({ value: 'cuda', label: 'CUDA', disabled: !hardwareInfo.platform_device_map.cuda })
      opts.push({ value: 'mps', label: 'MPS', disabled: !hardwareInfo.platform_device_map.mps })
      opts.push({ value: 'cpu', label: 'CPU', disabled: false })
    } else {
      opts[0].label = '自动'
      opts.push({ value: 'cuda', label: 'CUDA', disabled: true })
      opts.push({ value: 'mps', label: 'MPS', disabled: true })
      opts.push({ value: 'cpu', label: 'CPU', disabled: false })
    }
    return opts
  }

  $effect(() => {
    // If current selection becomes unavailable, reset to auto
    if (hardwareInfo) {
      const opts = getDeviceOptions()
      const cur = opts.find(o => o.value === config?.device)
      if (cur?.disabled) {
        config.device = 'auto'
      }
    }
  })

  function labelFor(value) {
    const labels = {
      cuda: 'CUDA',
      mps: 'MPS',
      cpu: 'CPU',
    }
    if (value === 'auto' && hardwareInfo) return `自动 (${hardwareInfo.device.toUpperCase()})`
    return labels[value] || value
  }
</script>

{#if loading}
  <p class="loading-text">加载中...</p>
{:else if config}
  <div class="settings">
    <!-- Hardware -->
    <div class="section">
      <h3>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        硬件
      </h3>

      {#if hardwareInfo}
        <div class="hw-info">
          <div class="hw-row">
            <span class="hw-key">检测设备</span>
            <span class="hw-val">{hardwareInfo.device_name}</span>
          </div>
          <div class="hw-row">
            <span class="hw-key">推理设备</span>
            <span class="hw-val">{hardwareInfo.device.toUpperCase()}</span>
          </div>
          <div class="hw-row">
            <span class="hw-key">可用显存</span>
            <span class="hw-val">{hardwareInfo.vram_gb.toFixed(1)} GB</span>
          </div>
          <div class="hw-row">
            <span class="hw-key">推荐模型</span>
            <span class="hw-val">{hardwareInfo.recommended_size}</span>
          </div>
        </div>

        {#if hardwareInfo.warnings?.length}
          {#each hardwareInfo.warnings as w}
            <div class="hw-warning">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <span>{w}</span>
            </div>
          {/each}
        {/if}

        {#if !hardwareInfo.can_run_asr}
          <div class="hw-warning severe">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span>当前硬件无法进行本地推理。请考虑使用 CPU 模式（速度较慢）或更换设备。</span>
          </div>
        {/if}
      {:else}
        <p class="loading-text">正在检测硬件...</p>
      {/if}

      <div class="settings-grid">
        <div class="field">
          <span class="field-label">推理设备</span>
          <select bind:value={config.device}>
            {#each getDeviceOptions() as opt}
              <option value={opt.value} disabled={opt.disabled}>{opt.label}</option>
            {/each}
          </select>
        </div>
        <div class="field">
          <span class="field-label">精度</span>
          <select bind:value={config.dtype}>
            <option value="bfloat16">bfloat16</option>
            <option value="float16">float16</option>
            <option value="float32">float32</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Model -->
    <div class="section">
      <h3>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        模型
      </h3>
      {#each models as m}
        <div class="model-row">
          <div class="model-info">
            <span class="model-name">{m.name}</span>
            <span class="model-type">{m.type === 'asr' ? 'ASR' : '对齐'}</span>
            <span class="model-size">{m.size_gb}GB</span>
          </div>
          <div class="model-actions">
            {#if m.downloaded}
              <span class="badge-ok">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                已下载
              </span>
            {:else}
              <button class="btn-download" onclick={() => downloadModel(m.id)}>下载</button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <!-- LLM -->
    <div class="section">
      <h3>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5"/><path d="M8.5 8.5a5 5 0 0 0 7 7"/></svg>
        LLM 校正
      </h3>
      <label class="toggle-row">
        <input type="checkbox" bind:checked={config.llm_enabled} />
        <span class="toggle-track">
          <span class="toggle-thumb"></span>
        </span>
        <span class="toggle-label">启用 LLM 校正</span>
      </label>
      {#if config.llm_enabled}
        <div class="settings-grid">
          <div class="field">
            <span class="field-label">LLM 类型</span>
            <select bind:value={config.llm_type}>
              <option value="ollama">Ollama</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
        </div>
        {#if config.llm_type === 'ollama'}
          <div class="field">
            <span class="field-label">Ollama 地址</span>
            <input type="url" bind:value={config.ollama_endpoint} placeholder="http://localhost:11434" />
          </div>
          <div class="field">
            <span class="field-label">Ollama 模型</span>
            <input type="text" bind:value={config.ollama_model} placeholder="qwen2.5" />
          </div>
        {:else}
          <div class="field">
            <span class="field-label">API 地址</span>
            <input type="url" bind:value={config.openai_base_url} placeholder="https://api.openai.com/v1" />
          </div>
          <div class="field">
            <span class="field-label">API Key</span>
            <input type="text" bind:value={config.openai_api_key} placeholder="sk-..." />
          </div>
          <div class="field">
            <span class="field-label">模型</span>
            <input type="text" bind:value={config.openai_model} placeholder="gpt-4o-mini" />
          </div>
        {/if}

        <!-- test connection -->
        <div class="llm-test-row">
          <button class="btn-test" onclick={testLlmConnection} disabled={llmTesting}>
            {llmTesting ? '测试中...' : '测试连接'}
          </button>
          {#if llmTesting}
            <span class="test-spinner">⏳</span>
          {/if}
          {#if llmTestResult === true}
            <span class="test-ok">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              连接成功
            </span>
          {:else if llmTestResult === false}
            <span class="test-err">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              {llmTestError}
            </span>
          {/if}
        </div>
      {/if}
    </div>

    <div class="actions">
      <button class="btn-primary" onclick={save} disabled={saving}>
        {saving ? '保存中...' : '保存设置'}
      </button>
      {#if saved}
        <span class="saved-msg">已保存</span>
      {/if}
    </div>

    {#if error}
      <p class="error-msg">{error}</p>
    {/if}
  </div>
{/if}

<style>
  .loading-text { color: var(--text-muted); font-size: 0.85rem; margin: 0.5rem 0; }
  .settings { display: flex; flex-direction: column; gap: 1.25rem; }
  .section { padding-top: 0.75rem; border-top: 1px solid var(--border); }
  .section:first-child { border-top: none; padding-top: 0; }
  .section h3 {
    margin: 0 0 0.6rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .section h3 svg { opacity: 0.6; }

  /* Hardware info display */
  .hw-info {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    padding: 0.6rem 0.75rem;
    background: rgba(255,255,255,0.015);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 0.75rem;
  }
  .hw-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.82rem;
  }
  .hw-key { color: var(--text-muted); font-weight: 500; }
  .hw-val { color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
  .hw-warning {
    display: flex;
    align-items: flex-start;
    gap: 0.4rem;
    padding: 0.5rem 0.75rem;
    background: rgba(245, 158, 11, 0.06);
    border: 1px solid rgba(245, 158, 11, 0.12);
    border-radius: 8px;
    font-size: 0.78rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
    line-height: 1.4;
  }
  .hw-warning svg { flex-shrink: 0; margin-top: 1px; color: #f59e0b; }
  .hw-warning.severe { background: rgba(239, 68, 68, 0.06); border-color: rgba(239, 68, 68, 0.12); }
  .hw-warning.severe svg { color: var(--red); }

  .settings-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }
  .field { margin-bottom: 0.5rem; display: flex; flex-direction: column; gap: 0.3rem; }
  .field-label { font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }
  select, input {
    padding: 0.5rem 0.7rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-primary);
    font-size: 0.85rem;
    transition: all 0.25s ease;
    font-family: inherit;
  }
  select:focus, input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
  }
  select option:disabled { color: var(--text-muted); background: var(--bg-secondary); }

  .model-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.03);
  }
  .model-row:last-child { border-bottom: none; }
  .model-info { display: flex; align-items: center; gap: 0.5rem; }
  .model-name { font-size: 0.85rem; color: var(--text-primary); font-weight: 500; }
  .model-type { font-size: 0.7rem; color: var(--accent-secondary); background: var(--accent-secondary-dim); padding: 0.1rem 0.4rem; border-radius: 4px; }
  .model-size { font-size: 0.75rem; color: var(--text-muted); }
  .badge-ok {
    font-size: 0.75rem;
    color: var(--green);
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }
  .model-actions { display: flex; align-items: center; gap: 0.5rem; }
  .btn-download {
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--accent);
    transition: all 0.2s;
  }
  .btn-download:hover { border-color: var(--accent); background: var(--accent-dim); }
  .toggle-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    cursor: pointer;
    margin-bottom: 0.5rem;
  }
  .toggle-row input[type="checkbox"] { display: none; }
  .toggle-track {
    width: 36px; height: 20px;
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    position: relative;
    transition: background 0.25s ease;
    flex-shrink: 0;
  }
  .toggle-row input:checked + .toggle-track { background: var(--accent); }
  .toggle-thumb {
    position: absolute;
    top: 2px; left: 2px;
    width: 16px; height: 16px;
    border-radius: 50%;
    background: #fff;
    transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .toggle-row input:checked + .toggle-track .toggle-thumb { transform: translateX(16px); }
  .toggle-label { font-size: 0.85rem; color: var(--text-primary); }
  .actions { display: flex; align-items: center; gap: 0.75rem; padding-top: 0.25rem; }
  .saved-msg { font-size: 0.8rem; color: var(--green); }
  .error-msg { color: var(--red); font-size: 0.82rem; margin: 0.5rem 0 0; }
  .llm-test-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .btn-test {
    padding: 0.35rem 0.75rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    transition: all 0.2s;
  }
  .btn-test:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .btn-test:disabled { opacity: 0.5; cursor: not-allowed; }
  .test-spinner { font-size: 0.85rem; color: var(--text-muted); }
  .test-ok {
    font-size: 0.78rem;
    color: var(--green);
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
  .test-err {
    font-size: 0.78rem;
    color: #ef4444;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    word-break: break-all;
  }
  .test-err svg { flex-shrink: 0; }
</style>
