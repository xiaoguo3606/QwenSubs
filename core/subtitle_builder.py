"""Build subtitle files from word-level timestamps and user-confirmed text."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Type alias for subtitle entries
LineEntry = Tuple[str, float, float]


def _seconds_to_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_ass(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _seconds_to_vtt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:05.3f}"


def build_subtitles(
    lines: list[str],
    timestamps: list[dict],
    output_format: str = "srt",
) -> str:
    """Build subtitle content from user-confirmed lines and word timestamps."""
    subtitle_entries = _match_timestamps(lines, timestamps)
    logger.info(
        "build_subtitles: %d lines in, %d entries out, format=%s",
        len(lines), len(subtitle_entries), output_format,
    )
    if subtitle_entries:
        for i, (t, s, e) in enumerate(subtitle_entries):
            logger.info("  entry %d: text=%r  start=%.2f  end=%.2f", i, t, s, e)

    match output_format.lower():
        case "srt":
            return _format_srt(subtitle_entries)
        case "ass":
            return _format_ass(subtitle_entries)
        case "vtt":
            return _format_vtt(subtitle_entries)
        case _:
            raise ValueError(f"Unsupported format: {output_format}")


def _match_timestamps(
    lines: list[str],
    timestamps: list[dict],
) -> list[tuple[str, float, float]]:
    """Match each subtitle line to a contiguous range of word timestamps.

    Uses greedy character-by-character matching against the concatenated
    timestamp text to find start/end times for each line.
    """
    if not lines or not timestamps:
        return []
    sub = Subtitler(lines, timestamps)
    entries = sub.run()
    logger.info(
        "_match_timestamps: %d lines in, %d entries out (chars=%d, full_text_len=%d)",
        len(lines), len(entries), len(sub.chars), len(sub.full_text),
    )
    return entries


LineEntry = Tuple[str, float, float]


class Char:
    __slots__ = ("char", "start", "end")

    def __init__(self, char: str, start: float, end: float) -> None:
        self.char = char
        self.start = start
        self.end = end


class Subtitler:
    def __init__(self, lines: list[str], timestamps: list[dict]):
        self.lines: list[str] = lines
        self.chars: List[Char] = []

        for ts in timestamps:
            txt = ts["text"]
            n = len(txt)
            if n == 0:
                continue
            dur = (ts["end_time"] - ts["start_time"]) / n
            for i, ch in enumerate(txt):
                self.chars.append(Char(
                    char=ch.lower(),
                    start=ts["start_time"] + i * dur,
                    end=ts["start_time"] + (i + 1) * dur,
                ))

        self.full_text: str = "".join(c.char for c in self.chars)
        self.pos: int = 0
        logger.info("Subtitler: %d chars, full_text=%r", len(self.chars), self.full_text[:200])

    def run(self) -> list[LineEntry]:
        entries: list[LineEntry] = []
        for i, line in enumerate(self.lines):
            key, entry = self._match_one(line)
            if entry:
                entries.append(entry)
                logger.info("  run[%d] MATCHED: %r", i, line[:50])
            else:
                logger.warning("  run[%d] NO MATCH: %r  (pos=%d/%d)", i, line[:50], self.pos, len(self.chars))
        return entries

    def _match_one(self, line: str) -> tuple[str, LineEntry | None]:
        """Match one subtitle line against timestamp chars using substring
        search.  When the user edits text in the review editor the exact
        characters may change; this routine finds the longest prefix of
        the (normalised) line that still exists in the remaining timestamp
        text, so a partial edit only loses the edited suffix rather than
        starving every subsequent line."""
        target = self._normalize(line)
        if not target:
            return line, None

        pos = self._advance_past_whitespace()
        if pos >= len(self.chars):
            return line, None

        remaining = self.full_text[pos:]
        found_at = remaining.find(target)
        matched_len = len(target)

        if found_at < 0 and len(target) > 2:
            # Exact match failed — try matching a prefix.  Walk backwards
            # from full length so we keep as much context as possible.
            for plen in range(len(target) - 1, len(target) // 2, -1):
                found_at = remaining.find(target[:plen])
                if found_at >= 0:
                    matched_len = plen
                    logger.info("  _match_one prefix: %r matched at +%d (target was %r)",
                                target[:plen], found_at, target)
                    break

        if found_at < 0:
            # Edited line doesn't match timestamp text exactly.
            # Estimate timestamps proportionally and advance pos so
            # subsequent lines can still match.
            if pos < len(self.chars):
                remaining_chars = len(self.full_text) - pos
                est_chars = max(len(target), remaining_chars // max(len(self.lines) - self.lines.index(line), 1))
                end_pos = min(pos + est_chars, len(self.chars) - 1)
                entry = (line, self.chars[pos].start, self.chars[end_pos].end)
                self.pos = end_pos + 1
                logger.info("  _match_one estimated: %r (pos=%d, est_chars=%d, total=%d)",
                            target, pos, est_chars, remaining_chars)
                return line, entry
            return line, None

        start_idx = pos + found_at
        end_idx = start_idx + matched_len - 1
        self.pos = end_idx + 1

        # Extend end through trailing whitespace so the subtitle covers
        # any silent gap before the next word.
        nxt = self._advance_past_whitespace(self.pos)
        if nxt < len(self.chars):
            end_idx = max(end_idx, nxt - 1)

        return line, (line, self.chars[start_idx].start, self.chars[end_idx].end)

    def _advance_past_whitespace(self, pos: int | None = None) -> int:
        if pos is None:
            pos = self.pos
        while pos < len(self.chars) and self.chars[pos].char.isspace():
            pos += 1
        return pos

    @staticmethod
    def _normalize(s: str) -> str:
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"[，。！？、；：""''【】（）…—　,.!?;:\\-'\"«»]", "", s)
        return s.lower()


def _format_srt(entries: list[tuple[str, float, float]]) -> str:
    lines = []
    for i, (text, start, end) in enumerate(entries, 1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt(start)} --> {_seconds_to_srt(end)}")
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)


def _format_ass(entries: list[tuple[str, float, float]]) -> str:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "ScaledBorderAndShadow: yes\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default, Arial, 48, &H00FFFFFF, &H000000FF, "
        "&H00000000, &H00000000, 0, 0, 0, 0, 100, 100, 0, 0, 1, 2, 1, 2, "
        "10, 10, 10, 1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    lines = [header]
    for text, start, end in entries:
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass(start)},{_seconds_to_ass(end)},"
            f"Default,,0,0,0,,{text.strip()}"
        )
    return "\n".join(lines)


def _format_vtt(entries: list[tuple[str, float, float]]) -> str:
    lines = ["WEBVTT", ""]
    for text, start, end in entries:
        lines.append(
            f"{_seconds_to_vtt(start)} --> {_seconds_to_vtt(end)}"
        )
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)
