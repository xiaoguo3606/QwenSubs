"""Build API task results from pipeline output dicts."""

from __future__ import annotations

from backend.schemas import SubtitleEntry, TaskResultResponse, TimestampEntry


def _char_len(text: str) -> int:
    return len(text.replace(" ", ""))


def normalize_subtitle_entry(entry: dict) -> dict:
    return {
        "text": entry.get("text", ""),
        "start_time": float(entry.get("start_time", entry.get("start", 0.0))),
        "end_time": float(entry.get("end_time", entry.get("end", 0.0))),
    }


def build_subtitle_entries(
    text: str,
    timestamps: list[dict],
    raw_entries: list[dict] | None = None,
) -> list[dict]:
    if raw_entries:
        return [
            normalize_subtitle_entry(e)
            for e in raw_entries
            if (e.get("text") or "").strip()
        ]

    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return []
    if not timestamps:
        return [{"text": line, "start_time": 0.0, "end_time": 0.0} for line in lines]

    entries: list[dict] = []
    word_idx = 0
    for line in lines:
        target = _char_len(line)
        if word_idx >= len(timestamps):
            entries.append({"text": line, "start_time": 0.0, "end_time": 0.0})
            continue

        start_time = timestamps[word_idx]["start_time"]
        end_time = timestamps[word_idx]["end_time"]
        covered = 0
        while word_idx < len(timestamps) and covered < target:
            covered += _char_len(timestamps[word_idx].get("text", ""))
            end_time = timestamps[word_idx]["end_time"]
            word_idx += 1
        entries.append(
            {"text": line, "start_time": start_time, "end_time": end_time}
        )
    return entries


def task_result_from_dict(result: dict) -> TaskResultResponse:
    text = result.get("text", "")
    timestamps = result.get("timestamps", [])
    subtitle_entries = build_subtitle_entries(
        text,
        timestamps,
        result.get("subtitle_entries"),
    )
    return TaskResultResponse(
        text=text,
        timestamps=[TimestampEntry(**t) for t in timestamps],
        subtitle_entries=[SubtitleEntry(**e) for e in subtitle_entries],
    )
