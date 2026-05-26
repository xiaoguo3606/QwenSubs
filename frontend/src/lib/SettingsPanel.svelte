<script>
  import { onMount } from 'svelte'

  let config = $state(null)
  let models = $state([])
  let loading = $state(true)
  let saving = $state(false)
  let saved = $state(false)
  let error = $state('')

  async function loadConfig() {
    try {
      const [c, m] = await Promise.all([
        fetch('/api/config').then(r => r.json()),
        fetch('/api/models').then(r => r.json()),
      ])
      config = c
      models = m.models
    } catch (e) {
      error = '加载配置失败: ' + (e.message || '')
    } finally {
      loading = false
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
      // Poll until download completes
      const poll = setInterval(async () => {
        try {
          const st = await fetch(`/api/tasks/${task_id}`).then(r => r.json())
          if (st.status === 'completed') {
            clearInterval(poll)
            loadConfig()
          } else if (st.status === 'failed' || st.status === 'cancelled') {
            clearInterval(poll)
            error = '下载失败: ' + (st.error || st.status)
          }
        } catch (e) { /* ignore */ }
      }, 2000)
    } catch (e) {
      error = '启动下载失败: ' + (e.message || '')
    }
  }

  onMount(loadConfig)
</script>

{#if loading}
  <p class="loading-text">加载中...</p>
{:else if config}
  <div class="settings">
    <!-- Model -->
    <div class="section">
      <h3>模型</h3>
      {#each models as m}
        <div class="model-row">
          <div class="model-info">
            <span class="model-name">{m.name}</span>
            <span class="model-type">{m.type === 'asr' ? 'ASR' : '对齐'}</span>
            <span class="model-size">{m.size_gb}GB</span>
          </div>
          <div class="model-actions">
            {#if m.downloaded}
              <span class="badge-ok">已下载</span>
            {:else}
              <button class="btn-sm btn-primary" onclick={() => downloadModel(m.id)}>下载</button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    <!-- Hardware -->
    <div class="section">
      <h3>硬件</h3>
      <div class="field">
        <span class="field-label">设备</span>
        <select bind:value={config.device}>
          <option value="auto">自动</option>
          <option value="cuda">CUDA</option>
          <option value="mps">MPS</option>
          <option value="cpu">CPU</option>
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

    <!-- LLM -->
    <div class="section">
      <h3>LLM 校正</h3>
      <label class="toggle-row">
        <input type="checkbox" bind:checked={config.llm_enabled} />
        启用 LLM 校正
      </label>
      {#if config.llm_enabled}
        <div class="field">
          <span class="field-label">LLM 类型</span>
          <select bind:value={config.llm_type}>
            <option value="ollama">Ollama</option>
            <option value="openai">OpenAI</option>
          </select>
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
      <p class="error">{error}</p>
    {/if}
  </div>
{/if}

<style>
  .loading-text { color: var(--text-muted); font-size: 0.85rem; margin: 0.5rem 0; }
  .settings { display: flex; flex-direction: column; gap: 1rem; }
  .section { border-top: 1px solid var(--border); padding-top: 0.75rem; }
  .section:first-child { border-top: none; padding-top: 0; }
  .section h3 { margin: 0 0 0.6rem; font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
  .field { margin-bottom: 0.5rem; }
  .field-label { display: block; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem; }
  .model-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.45rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .model-row:last-child { border-bottom: none; }
  .model-info { display: flex; align-items: center; gap: 0.5rem; }
  .model-name { font-size: 0.85rem; color: var(--text-primary); }
  .model-type { font-size: 0.72rem; color: var(--accent); background: var(--accent-dim); padding: 0.1rem 0.4rem; border-radius: 4px; }
  .model-size { font-size: 0.75rem; color: var(--text-muted); }
  .badge-ok { font-size: 0.75rem; color: var(--green); }
  .model-actions { display: flex; align-items: center; gap: 0.5rem; }
  .btn-sm {
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }
  .btn-primary { background: var(--gradient-2); color: #fff; }
  .btn-primary:disabled { opacity: 0.35; cursor: not-allowed; }
  .toggle-row { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: var(--text-primary); cursor: pointer; }
  .toggle-row input[type="checkbox"] { accent-color: var(--accent); width: 14px; height: 14px; margin: 0; }
  .actions { display: flex; align-items: center; gap: 0.75rem; padding-top: 0.5rem; }
  .saved-msg { font-size: 0.8rem; color: var(--green); }
  .error { color: var(--red); font-size: 0.82rem; margin: 0.5rem 0 0; }
</style>
