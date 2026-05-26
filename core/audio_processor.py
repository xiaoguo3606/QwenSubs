import os
import tempfile
import subprocess
from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"}

MAX_AUDIO_DURATION = 300.0  # 5 minutes


def is_audio_file(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in AUDIO_EXTENSIONS


def convert_to_16k_mono(input_path: str, output_path: str | None = None) -> str:
    """Convert audio to 16kHz mono WAV using ffmpeg."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="qwen_asr_")
        os.close(fd)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-sample_fmt", "s16",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return output_path


def extract_audio_segment(wav_path: str, start_sec: float, duration_sec: float) -> str:
    """Extract a segment of audio to a temp 16kHz mono WAV file."""
    fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="qwen_seg_")
    os.close(fd)
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
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return output_path


def split_audio(wav_path: str, max_duration: float = 180.0) -> list[tuple[str, float, float]]:

    """Split a WAV file into chunks of at most max_duration seconds.

    Returns list of (chunk_path, chunk_start_time_seconds, chunk_duration_seconds).
    The first chunk's start_time is 0.0; subsequent chunks start at max_duration boundaries.
    If the audio is shorter than max_duration, returns [(wav_path, 0.0, duration)].
    """
    duration = get_audio_duration(wav_path)
    if duration <= max_duration:
        return [(wav_path, 0.0, duration)]

    chunks = []
    start = 0.0
    idx = 0
    while start < duration:
        actual = min(max_duration, duration - start)
        fd, chunk_path = tempfile.mkstemp(suffix=".wav", prefix=f"qwen_chunk_{idx}_")
        os.close(fd)

        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-ss", str(start),
            "-t", str(actual),
            "-ar", "16000",
            "-ac", "1",
            "-sample_fmt", "s16",
            chunk_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        chunks.append((chunk_path, start, actual))
        start += actual
        idx += 1

    return chunks


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
    return float(result.stdout.strip())


def detect_speech_duration(wav_path: str, frame_ms: int = 50, threshold: float = 0.005) -> float:
    """Estimate the duration of non-silent portions of a WAV file.

    Reads audio with ``soundfile``, computes RMS energy in non-overlapping
    windows, and returns the range from the first to the last window whose
    RMS exceeds *threshold*.

    Returns the full file duration if no silence is detected (conservative).
    """
    import math
    import soundfile as sf

    data, sr = sf.read(wav_path)
    if data.ndim > 1:
        data = data.mean(axis=1)  # mono mix

    frame_samples = sr * frame_ms // 1000

    # Sum actual active-frame durations (not span from first to last)
    total_active = 0.0
    for start in range(0, len(data), frame_samples):
        frame = data[start:start + frame_samples]
        if len(frame) == 0:
            continue
        rms = math.sqrt((frame * frame).mean())
        if rms > threshold:
            total_active += len(frame) / sr

    return total_active if total_active > 0 else len(data) / sr

