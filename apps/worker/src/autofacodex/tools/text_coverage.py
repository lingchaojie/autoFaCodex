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


def _missing_text(source_text: str, candidate: str) -> str:
    missing: list[str] = []
    for word in re.findall(r"[A-Za-z0-9]+", source_text):
        normalized_word = normalize_text(word)
        if normalized_word and normalized_word not in candidate:
            missing.append(normalized_word)

    source = normalize_text(source_text)
    covered = "".join(missing)
    for char in source:
        if char.isascii() and char.isalnum():
            continue
        if char not in candidate:
            covered += char
    return covered


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
    if source in candidate:
        return {
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": len(source),
            "candidate_length": len(candidate),
        }
    missing = _missing_text(source_text, candidate)
    missing_ratio = len(missing) / len(source)
    score = max(0.0, min(1.0, 1.0 - missing_ratio))
    return {
        "score": score,
        "missing_ratio": missing_ratio,
        "missing_text": missing,
        "source_length": len(source),
        "candidate_length": len(candidate),
    }
