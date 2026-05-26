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
      <div>
        <h1>Qwen ASR 字幕工具</h1>
        <p class="subtitle">基于 Qwen3-ASR 的智能字幕生成</p>
      </div>
      <div class="header-actions">
        <button class="btn-icon" onclick={toggleTheme} title={darkTheme ? '切换亮色主题' : '切换暗色主题'}>
          {#if darkTheme}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"/>
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
          {:else}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
            </svg>
          {/if}
        </button>
        <button class="btn-icon" onclick={() => showSettings = !showSettings} title="设置">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
        </button>
      </div>
    </div>
  </header>

  {#if showSettings}
    <section class="card">
      <div class="card-title-row">
        <h2 class="card-title" style="margin:0">设置</h2>
        <button class="btn-sm btn-ghost" onclick={() => showSettings = false}>关闭</button>
      </div>
      <SettingsPanel />
    </section>
  {/if}

  <main class="app-main">
    <section class="card">
      <h2 class="card-title"><span class="step-badge">1</span>上传音频</h2>
      <AudioUploader />
    </section>

    {#if $audioUrl}
      <section class="card">
        <h2 class="card-title"><span class="step-badge">2</span>音频波形</h2>
        <Waveform audioUrl={$audioUrl} duration={audioDuration} timestamps={$timestamps} subtitleEntries={$subtitleEntries} focusTime={seekTarget} />
      </section>
    {/if}

    {#if $audioUrl}
      <section class="card">
        <h2 class="card-title"><span class="step-badge">3</span>选择处理方式</h2>
        <div class="mode-selector">
          <button
            class="mode-btn {$mode === 'asr' ? 'active' : ''}"
            onclick={() => mode.set('asr')}
          >
            <span class="mode-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </span>
            <span class="mode-name">语音识别 (ASR)</span>
            <span class="mode-desc">自动识别音频中的语音，生成字幕文本和时间轴</span>
          </button>
          <button
            class="mode-btn {$mode === 'align' ? 'active' : ''}"
            onclick={() => mode.set('align')}
          >
            <span class="mode-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="4 7 4 4 20 4 20 7"/>
                <line x1="9" y1="20" x2="15" y2="20"/>
                <line x1="12" y1="4" x2="12" y2="20"/>
                <line x1="4" y1="11" x2="20" y2="11"/>
                <line x1="4" y1="16" x2="20" y2="16"/>
              </svg>
            </span>
            <span class="mode-name">强制对齐 (Alignment)</span>
            <span class="mode-desc">将已有文本与音频对齐，修正时间轴精度</span>
          </button>
        </div>
      </section>
    {/if}

    {#if $audioUrl && $mode === 'asr'}
      <section class="card">
        <h2 class="card-title"><span class="step-badge">3b</span>语音识别</h2>
        <AsrPanel />
      </section>
    {/if}

    {#if $audioUrl && $mode === 'align'}
      <section class="card">
        <h2 class="card-title"><span class="step-badge">3b</span>强制对齐</h2>
        <AlignPanel />
      </section>
    {/if}

    {#if $subtitleText}
      <section class="card">
        <h2 class="card-title"><span class="step-badge">4</span>字幕编辑</h2>
        <SubtitleEditor bind:this={editorEl} text={$subtitleText} timestamps={$timestamps} onseek={onSeek} />
      </section>

      <section class="card">
        <h2 class="card-title"><span class="step-badge">5</span>导出</h2>
        <ExportPanel bind:this={exportPanel} />
      </section>
    {/if}
  </main>
</div>

<style>
  .header-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }
  .header-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }
  .btn-icon {
    background: none;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 0.4rem;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 0.25rem;
  }
  .btn-icon:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }
  .card-title-row { display: flex; align-items: center; justify-content: space-between; }
  .btn-sm {
    padding: 0.35rem 0.8rem;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-secondary);
    transition: all 0.2s;
  }
  .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }

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
    padding: 1.25rem 1rem;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: rgba(13, 13, 36, 0.4);
    cursor: pointer;
    transition: all 0.25s;
    text-align: center;
  }
  .mode-btn:hover {
    border-color: rgba(79, 195, 247, 0.3);
    background: rgba(79, 195, 247, 0.05);
  }
  .mode-btn.active {
    border-color: var(--accent);
    background: rgba(79, 195, 247, 0.1);
    box-shadow: 0 0 20px rgba(79, 195, 247, 0.1);
  }
  .mode-icon { color: var(--accent); display: flex; }
  .mode-name { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); }
  .mode-desc { font-size: 0.78rem; color: var(--text-muted); line-height: 1.4; }
</style>
