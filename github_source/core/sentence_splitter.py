"""Split text into sentences at every punctuation boundary."""

from __future__ import annotations

# Punctuation marks that trigger a sentence split.
# Note: ASCII apostrophe (') and curly quotes ('') are deliberately excluded
# so English contractions like "don't" are not split.
SPLIT_MARKS = set("，。！？、；：""「」『』【】（）()《》<>.!?,;:…—～")

# Also split at newlines
SPLIT_MARKS.add("\n")


def split_sentences(text: str) -> list[str]:
    """Split text at every punctuation mark. Each mark ends one subtitle line."""
    if not text.strip():
        return []

    lines = []
    current = []

    for ch in text:
        current.append(ch)
        if ch in SPLIT_MARKS:
            line = "".join(current).strip()
            if line:
                lines.append(line)
            current = []

    if current:
        remaining = "".join(current).strip()
        if remaining:
            lines.append(remaining)

    return lines
