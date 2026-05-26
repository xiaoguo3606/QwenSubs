<script>
  import WaveSurfer from 'wavesurfer.js'
  import { playbackTime } from './stores.js'

  let { audioUrl, duration, splitPoint, timestamps = [], focusTime = null, subtitleEntries = [] } = $props()

  let container
  let wavesurfer
  let isReady = $state(false)
  let isPlaying = $state(false)
  let currentTime = $state(0)

  export function getCurrentTime() {
    return wavesurfer?.getCurrentTime() ?? 0
  }

  export function seekTo(time) {
    wavesurfer?.setTime(time)
  }

  export function getWavesurfer() {
    return wavesurfer
  }

  $effect(() => {
    if (focusTime != null && wavesurfer && isReady) {
      wavesurfer.setTime(focusTime)
    }
  })

  $effect(() => {
    if (!audioUrl || !container) return

    if (!wavesurfer) {
      wavesurfer = WaveSurfer.create({
        container,
        waveColor: 'rgba(79, 195, 247, 0.35)',
        progressColor: 'rgba(79, 195, 247, 0.8)',
        cursorColor: 'rgba(255, 255, 255, 0.5)',
        barWidth: 2,
        barRadius: 3,
        height: 100,
        normalize: true,
      })

      wavesurfer.on('ready', () => {
        isReady = true
        duration.set(wavesurfer.getDuration())
      })

      wavesurfer.on('timeupdate', (t) => {
        currentTime = t
        playbackTime.set(t)
      })
      wavesurfer.on('play', () => isPlaying = true)
      wavesurfer.on('pause', () => isPlaying = false)
    }

    wavesurfer.load(audioUrl)

    return () => {
      if (wavesurfer) {
        wavesurfer.destroy()
        wavesurfer = null
        isReady = false
      }
    }
  })

  function togglePlay() {
    wavesurfer?.playPause()
  }

  function formatTime(t) {
    if (t == null || isNaN(t)) return '0:00'
    const m = Math.floor(t / 60)
    const s = Math.floor(t % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }
</script>

<div class="waveform-container">
  <div bind:this={container} class="waveform"></div>

  {#if !isReady && audioUrl}
    <div class="loading">加载波形...</div>
  {/if}

  <div class="controls">
    <div class="controls-left">
      <button class="play-btn" onclick={togglePlay} disabled={!isReady} title={isPlaying ? '暂停' : '播放'}>
        {#if isPlaying}
          <span class="pause-icon"></span>
        {:else}
          <span class="play-icon"></span>
        {/if}
      </button>

      <div class="time-info">
        <span class="time-label">当前</span>
        <span class="time-value">{formatTime(currentTime)}</span>
      </div>
    </div>

    <div class="controls-right">
      <div class="time-info">
        <span class="time-label">总时长</span>
        <span class="time-value">{formatTime($duration)}</span>
      </div>
    </div>
  </div>
</div>

<style>
  .waveform-container {
    position: relative;
    width: 100%;
    margin: 0.5rem 0;
  }
  .waveform { width: 100%; }
  .loading {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-muted); font-size: 0.85rem;
  }
  .controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.6rem;
  }
  .controls-left {
    display: flex;
    align-items: center;
    gap: 1rem;
  }
  .controls-right {
    display: flex;
    align-items: center;
  }
  .play-btn {
    width: 34px; height: 34px;
    flex-shrink: 0;
    aspect-ratio: 1;
    overflow: hidden;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.06);
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  .play-btn:hover:not(:disabled) { border-color: var(--accent); background: var(--accent-dim); }
  .play-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  .play-icon {
    width: 0;
    height: 0;
    border-top: 7px solid transparent;
    border-bottom: 7px solid transparent;
    border-left: 12px solid currentColor;
    margin-left: 4px;
  }
  .pause-icon {
    display: block;
    width: 4px;
    height: 14px;
    background: currentColor;
    border-radius: 1px;
    box-shadow: 7px 0 0 0 currentColor;
  }

  .time-info { display: flex; align-items: center; gap: 0.35rem; }
  .time-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; }
  .time-value {
    font-size: 0.85rem; font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    min-width: 3.2rem;
  }
</style>
