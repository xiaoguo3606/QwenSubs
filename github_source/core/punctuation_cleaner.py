import re

# Punctuation marks stripped from end of each subtitle line
TRAILING_PUNCT = "。！？，、；：…～.!?,;:"


def strip_trailing_punctuation(text: str) -> str:
    """Strip trailing punctuation from each line of multi-line text."""
    lines = text.split("\n")
    lines = [line.rstrip(TRAILING_PUNCT) for line in lines]
    return "\n".join(lines)


def capitalize_lines(text: str) -> str:
    """Capitalize the first alphabetic character of each line."""
    def _capitalize(line: str) -> str:
        match = re.search(r'[a-zA-Z]', line)
        if match:
            i = match.start()
            return line[:i] + line[i].upper() + line[i + 1:]
        return line

    lines = text.split("\n")
    lines = [_capitalize(line) for line in lines]
    return "\n".join(lines)


# Mid-sentence punctuation type → characters to remove
MID_PUNCTUATION_MAP = {
    "单引号": "'‘’＇",
    "双引号": "\"“”＂",
    "书名号": "《》〈〉",
    "冒号": ":：",
    "顿号": "、",
    "正反斜杠": "\\/／＼",
    "破折号": "—―",
    "间隔号": "·・",
    "连接号": "-–－",
    "下划线": "_＿",
}
ALL_MID_TYPES = list(MID_PUNCTUATION_MAP.keys())


def strip_mid_punctuation(
    text: str, selected_types: list[str], replace_with_space: bool = False
) -> str:
    """Remove or replace selected mid-sentence punctuation from each line."""
    if not selected_types:
        return text

    if "以上全部" in selected_types:
        selected_types = ALL_MID_TYPES

    chars = ""
    for t in selected_types:
        if t in MID_PUNCTUATION_MAP:
            chars += MID_PUNCTUATION_MAP[t]

    if not chars:
        return text

    replacement = " " if replace_with_space else ""
    pattern = f"[{re.escape(chars)}]"

    lines = text.split("\n")
    lines = [re.sub(pattern, replacement, line) for line in lines]

    if replace_with_space:
        lines = [re.sub(r" +", " ", line).strip() for line in lines]

    return "\n".join(lines)


def clean_punctuation(text: str, chars_to_remove: str | None = None) -> str:
    """Remove specified punctuation characters from text.

    If chars_to_remove is None or empty, remove all common punctuation.
    Otherwise remove only the characters specified.
    """
    if not text:
        return text

    if chars_to_remove:
        pattern = f"[{re.escape(chars_to_remove)}]"
        return re.sub(pattern, "", text)

    # Default: remove all common Chinese + English punctuation
    common = (
        "，。！？、；：""''""「」『』【】（）()〔〕"
        "<>.。,\"'!?;:()[]{}…—～·"
    )
    pattern = f"[{re.escape(common)}]"
    return re.sub(pattern, "", text)
