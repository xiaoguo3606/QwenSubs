"""Audio processing utilities using ffmpeg/ffprobe with Python fallbacks."""

import os
import subprocess
import tempfile
from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"}

MAX_AUDIO_DURATION = 300.0  # 5 minutes


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _ffprobe_available() -> bool:
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def is_audio_file(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in AUDIO_EXTENSIONS


def convert_to_16k_mono(input_path: str, output_path: str | None = None) -> str:
    """Convert audio to 16kHz mono WAV.

    Uses ffmpeg if available; otherwise falls back to pydub (for WAV/FLAC/OGG)
    or raises a clear error.
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="qwen_asr_")
        os.close(fd)

    # Try ffmpeg first
    if _ffmpeg_available():
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-sample_fmt", "s16",
            output_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            return output_path
        except subprocess.CalledProcessError:
            pass  # fall through to fallback

    # Fallback: try pydub (handles WAV natively; needs ffmpeg for mp3/m4a etc.)
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(output_path, format="wav")
        return output_path
    except Exception:
        pass

    # Give up with a helpful message
    ext = Path(input_path).suffix.lower()
    if ext in (".wav", ".flac", ".ogg"):
        msg = (
            "Audio conversion requires ffmpeg or pydub+libav. "
            "Install ffmpeg: https://ffmpeg.org/download.html"
        )
    else:
        msg = (
            "Audio conversion requires ffmpeg. "
            f"Format '{ext}' cannot be processed without ffmpeg.\n"
            "Install ffmpeg: https://ffmpeg.org/download.html"
        )
    raise RuntimeError(msg)


def _duration_via_ffprobe(path: str) -> float | None:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
        return float(result.stdout.strip())
    except Exception:
        return None


def _duration_via_soundfile(path: str) -> float | None:
    try:
        import soundfile as sf
        info = sf.info(path)
        return info.duration
    except Exception:
        return None


def _duration_via_wave(path: str) -> float | None:
    import wave
    try:
        with wave.open(path, "r") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds.

    Tries ffprobe → soundfile → stdlib wave, then raises.
    """
    duration = _duration_via_ffprobe(path)
    if duration is not None:
        return duration

    duration = _duration_via_soundfile(path)
    if duration is not None:
        return duration

    duration = _duration_via_wave(path)
    if duration is not None:
        return duration

    raise RuntimeError(
        "Could not determine audio duration. "
        "Install ffmpeg: https://ffmpeg.org/download.html"
    )


def extract_audio_segment(wav_path: str, start_sec: float, duration_sec: float) -> str:
    """Extract a segment of audio to a temp 16kHz mono WAV file."""
    fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="qwen_seg_")
    os.close(fd)

    if _ffmpeg_available():
        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-ar", "16000",
            "-ac", "1",
            "-sample_fmt", "s16",
            output_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            return output_path
        except subprocess.CalledProcessError:
            pass

    # Fallback: use pydub on the WAV file
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(wav_path, format="wav")
        seg = audio[start_sec * 1000 : (start_sec + duration_sec) * 1000]
        seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        seg.export(output_path, format="wav")
        return output_path
    except Exception:
        raise RuntimeError(
            "Audio segment extraction requires ffmpeg or pydub. "
            "Install ffmpeg: https://ffmpeg.org/download.html"
        )


def split_audio(wav_path: str, max_duration: float = 180.0) -> list[tuple[str, float, float]]:
    """Split a WAV file into chunks of at most max_duration seconds."""
    duration = get_audio_duration(wav_path)
    if duration <= max_duration:
        return [(wav_path, 0.0, duration)]

    chunks = []
    start = 0.0
    idx = 0
    while start < duration:
        actual = min(max_duration, duration - start)
        chunk = extract_audio_segment(wav_path, start, actual)
        chunks.append((chunk, start, actual))
        start += actual
        idx += 1

    return chunks


def detect_speech_duration(wav_path: str, frame_ms: int = 50, threshold: float = 0.005) -> float:
    """Estimate the duration of non-silent portions of a WAV file."""
    import math
    import struct

    try:
        import soundfile as sf
        data, sr = sf.read(wav_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        is_numpy = True
    except Exception:
        import wave
        with wave.open(wav_path, "r") as wf:
            sr = wf.getframerate()
            nframes = wf.getnframes()
            frames = wf.readframes(nframes)
            # Convert raw bytes to floats without numpy
            dtype = wf.getsampwidth()
            count = nframes * wf.getnchannels()
            if dtype == 2:  # 16-bit
                fmt = f"<{count}h"
            elif dtype == 1:  # 8-bit
                fmt = f"<{count}B"
            elif dtype == 4:  # 32-bit
                fmt = f"<{count}i"
            else:
                raise ValueError(f"Unsupported sample width: {dtype}")
            raw = struct.unpack(fmt, frames)
            # 16-bit -> float
            scale = 1.0 / (1 << (dtype * 8 - 1))
            data = [s * scale for s in raw]
            if wf.getnchannels() > 1:
                data = [data[i] for i in range(0, len(data), wf.getnchannels())]
        is_numpy = False

    frame_samples = sr * frame_ms // 1000
    total_active = 0.0
    n = len(data)
    for start in range(0, n, frame_samples):
        end = min(start + frame_samples, n)
        frame = data[start:end]
        if len(frame) == 0:
            continue
        sq_sum = sum(x * x for x in frame) / len(frame)
        rms = math.sqrt(sq_sum)
        if rms > threshold:
            total_active += len(frame) / sr

    return total_active if total_active > 0 else n / sr
