from collections import Counter
import re
import unicodedata


PUNCT_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "！": "!",
        "？": "?",
    }
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.translate(PUNCT_TRANSLATION).lower()
    return re.sub(r"\s+", "", normalized)


ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def _normalize_for_tokens(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return normalized.translate(PUNCT_TRANSLATION).lower()


def _normalized_ascii_tokens(value: str) -> list[str]:
    return ASCII_TOKEN_PATTERN.findall(_normalize_for_tokens(value))


def _missing_coverage(source_text: str, candidate_text: str) -> tuple[int, str]:
    candidate_tokens = Counter(_normalized_ascii_tokens(candidate_text))
    missing_tokens: list[str] = []
    missing_count = 0
    for token in _normalized_ascii_tokens(source_text):
        if candidate_tokens[token] > 0:
            candidate_tokens[token] -= 1
        else:
            missing_tokens.append(token)
            missing_count += len(token)

    candidate_non_ascii = Counter(
        char for char in normalize_text(candidate_text) if not (char.isascii() and char.isalnum())
    )
    missing_chars: list[str] = []
    for char in normalize_text(source_text):
        if char.isascii() and char.isalnum():
            continue
        if candidate_non_ascii[char] > 0:
            candidate_non_ascii[char] -= 1
        else:
            missing_chars.append(char)
            missing_count += 1

    return missing_count, "".join(missing_tokens + missing_chars)


def compare_text_coverage(source_text: str, candidate_text: str) -> dict:
    source = normalize_text(source_text)
    candidate = normalize_text(candidate_text)
    if not source:
        return {
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": 0,
            "candidate_length": len(candidate),
        }
    if source == candidate:
        return {
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": len(source),
            "candidate_length": len(candidate),
        }
    missing_count, missing_text = _missing_coverage(source_text, candidate_text)
    missing_ratio = missing_count / len(source)
    score = max(0.0, min(1.0, 1.0 - missing_ratio))
    return {
        "score": score,
        "missing_ratio": missing_ratio,
        "missing_text": missing_text,
        "source_length": len(source),
        "candidate_length": len(candidate),
    }
