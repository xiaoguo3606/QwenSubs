<script>
  import AudioUploader from './lib/AudioUploader.svelte'
  import Waveform from './lib/Waveform.svelte'
  import AsrPanel from './lib/AsrPanel.svelte'
  import AlignPanel from './lib/AlignPanel.svelte'
  import SubtitleEditor from './lib/SubtitleEditor.svelte'
  import ExportPanel from './lib/ExportPanel.svelte'
  import SettingsPanel from './lib/SettingsPanel.svelte'
  import { audioUrl, audioDuration, subtitleText, timestamps, subtitleEntries, mode } from './lib/stores.js'

  let editorEl = $state(null)
  let exportPanel = $state(null)
  let showSettings = $state(false)
  let seekTarget = $state(null)
  let darkTheme = $state(true)

  function toggleTheme() {
    darkTheme = !darkTheme
    document.documentElement.classList.toggle('light', !darkTheme)
  }

  function onSeek(time) {
    seekTarget = time
  }

  $effect(() => {
    if (editorEl && exportPanel) {
      exportPanel.setEditor(editorEl)
    }
  })
</script>

<div class="app-container">
  <header class="app-header">
    <div class="header-row">
      <div class="header-text">
        <h1>QwenSubs <span class="version">V0.0.2</span></h1>
        <p class="subtitle">基于 <em>Qwen3-ASR</em> 的字幕生成助手，中文友好，专为精准的中文字幕设计。</p>
      </div>
      <div class="header-actions">
        <button class="btn-icon" onclick={toggleTheme} title={darkTheme ? '切换亮色主题' : '切换暗色主题'}>
          {#if darkTheme}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="5"/>
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
          {:else}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
            </svg>
          {/if}
        </button>
        <button class="btn-icon" onclick={() => showSettings = !showSettings} title="设置">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
        </button>
      </div>
    </div>
  </header>

  {#if showSettings}
    <section class="card">
      <div class="step-wrap" style="margin-bottom: 1rem;">
        <span class="step-badge" style="background: var(--accent-secondary-dim); color: var(--accent-secondary); border-color: rgba(6,182,212,0.2);">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
        </span>
        <span class="step-label">设置</span>
        <button class="btn-ghost btn-sm" style="margin-left: auto;" onclick={() => showSettings = false}>关闭</button>
      </div>
      <SettingsPanel />
    </section>
  {/if}

  <main class="app-main">
    <section class="card">
      <div class="step-wrap">
        <span class="step-badge">1</span>
        <span class="step-label">上传音频</span>
      </div>
      <AudioUploader />
    </section>

    {#if $audioUrl}
      <section class="card">
        <div class="step-wrap">
          <span class="step-badge">2</span>
          <span class="step-label">音频波形</span>
        </div>
        <Waveform audioUrl={$audioUrl} duration={audioDuration} timestamps={$timestamps} subtitleEntries={$subtitleEntries} focusTime={seekTarget} />
      </section>
    {/if}

    {#if $audioUrl}
      <section class="card">
        <div class="step-wrap">
          <span class="step-badge">3</span>
          <span class="step-label">选择处理方式</span>
        </div>
        <div class="mode-selector">
          <button
            class="mode-btn {$mode === 'asr' ? 'active' : ''}"
            onclick={() => mode.set('asr')}
          >
            <span class="mode-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </span>
            <span class="mode-name">语音识别 <small>ASR</small></span>
            <span class="mode-desc">自动识别音频中的语音，生成字幕文本和时间轴</span>
          </button>
          <button
            class="mode-btn {$mode === 'align' ? 'active' : ''}"
            onclick={() => mode.set('align')}
          >
            <span class="mode-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4 7 4 4 20 4 20 7"/>
                <line x1="9" y1="20" x2="15" y2="20"/>
                <line x1="12" y1="4" x2="12" y2="20"/>
                <line x1="4" y1="11" x2="20" y2="11"/>
                <line x1="4" y1="16" x2="20" y2="16"/>
              </svg>
            </span>
            <span class="mode-name">强制对齐 <small>Alignment</small></span>
            <span class="mode-desc">将已有文本与音频对齐，修正时间轴精度</span>
          </button>
        </div>
      </section>
    {/if}

    {#if $audioUrl && $mode === 'asr'}
      <section class="card">
        <div class="step-wrap">
          <span class="step-badge" style="background: var(--accent-secondary-dim); color: var(--accent-secondary); border-color: rgba(6,182,212,0.2);">3b</span>
          <span class="step-label">语音识别</span>
        </div>
        <AsrPanel />
      </section>
    {/if}

    {#if $audioUrl && $mode === 'align'}
      <section class="card">
        <div class="step-wrap">
          <span class="step-badge" style="background: var(--accent-secondary-dim); color: var(--accent-secondary); border-color: rgba(6,182,212,0.2);">3b</span>
          <span class="step-label">强制对齐</span>
        </div>
        <AlignPanel />
      </section>
    {/if}

    {#if $subtitleText}
      <section class="card">
        <div class="step-wrap">
          <span class="step-badge">4</span>
          <span class="step-label">字幕编辑</span>
        </div>
        <SubtitleEditor bind:this={editorEl} text={$subtitleText} timestamps={$timestamps} onseek={onSeek} />
      </section>

      <section class="card">
        <div class="step-wrap">
          <span class="step-badge">5</span>
          <span class="step-label">导出</span>
        </div>
        <ExportPanel bind:this={exportPanel} />
      </section>
    {/if}
  </main>
</div>

<style>
  .mode-selector {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .mode-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1.35rem 1rem;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: transparent;
    cursor: pointer;
    transition: all 0.3s ease;
    text-align: center;
    color: var(--text-primary);
  }
  .mode-btn:hover {
    border-color: rgba(59, 130, 246, 0.2);
    background: rgba(59, 130, 246, 0.03);
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
  }
  .mode-btn.active {
    border-color: var(--accent);
    background: var(--accent-dim);
    box-shadow: 0 0 30px rgba(59, 130, 246, 0.08), 0 8px 25px rgba(0,0,0,0.3);
  }
  .mode-icon { color: var(--accent); display: flex; }
  .mode-btn.active .mode-icon { color: var(--accent); }
  .mode-name { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); }
  .mode-name small {
    font-weight: 400;
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-left: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .mode-desc { font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; max-width: 240px; }
</style>
